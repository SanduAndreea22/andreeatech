"""Share card for a project page: a 1200x630 image with the project's title,
direction, honest status label, stack and screenshot.

Why: when a project link is posted on LinkedIn or Facebook, the preview shows
this card instead of the generic brand card.

How it works
- `card_version(project, host)` is cheap (no drawing). It is a short hash of
  everything that appears on the card. The project page puts it in the og:image
  URL (`.../card.jpg?v=<hash>`), so a changed project gets a new URL and the
  networks fetch a fresh image instead of showing an old cached one.
- `ensure_card(project, host)` draws the card the first time it is needed and
  keeps the JPEG on disk under MEDIA_ROOT/share_cards/. Files are named after
  the version, so they never need invalidating: a changed project simply gets a
  new file, and the old ones for that project are removed.
- Nothing is stored in the database.

Only Pillow is used (already a dependency). The fonts are the site's own, as
.ttf files in website/share_fonts/. Fraunces and Hanken Grotesk are variable
fonts, so a weight is picked with set_variation_by_axes.
"""
import hashlib
import logging
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)

CARD_FORMAT_VERSION = "2"   # bump when the design changes, to redraw every card
WIDTH, HEIGHT = 1200, 630
FONT_DIR = Path(__file__).resolve().parent / "share_fonts"

# Colours of the site (tokens.css, light theme)
PAPER = (246, 246, 242)
PAPER_2 = (236, 236, 230)
INK = (17, 20, 42)
INK_2 = (70, 75, 102)
LINE = (214, 214, 204)
LINE_STRONG = (180, 183, 200)
BORDER_UI = (122, 127, 153)
COBALT = (47, 75, 219)
OK = (31, 107, 58)

# The "latin" subset covers these code points (copied from the unicode-range of
# static/website/fonts.css); anything else Romanian needs (ă ș ț) is in "latin-ext".
_LATIN = [(0x0000, 0x00FF), (0x0131, 0x0131), (0x0152, 0x0153), (0x02BB, 0x02BC), (0x02C6, 0x02C6),
          (0x02DA, 0x02DA), (0x02DC, 0x02DC), (0x0304, 0x0304), (0x0308, 0x0308), (0x0329, 0x0329),
          (0x2000, 0x206F), (0x20AC, 0x20AC), (0x2122, 0x2122), (0x2191, 0x2191), (0x2193, 0x2193),
          (0x2212, 0x2212), (0x2215, 0x2215), (0xFEFF, 0xFEFF), (0xFFFD, 0xFFFD)]
_LATIN_EXT = [(0x0100, 0x02BA), (0x02BD, 0x02C5), (0x02C7, 0x02CC), (0x02CE, 0x02D7), (0x02DD, 0x02FF),
              (0x0304, 0x0304), (0x0308, 0x0308), (0x0329, 0x0329), (0x1D00, 0x1DBF), (0x1E00, 0x1E9F),
              (0x1EF2, 0x1EFF), (0x2020, 0x2020), (0x20A0, 0x20AB), (0x20AD, 0x20C4), (0x2113, 0x2113),
              (0x2C60, 0x2C7F), (0xA720, 0xA7FF)]


def _in(ranges, code):
    return any(lo <= code <= hi for lo, hi in ranges)


def _clean(text):
    """One line of printable text the fonts can draw; anything else is dropped."""
    text = "".join(c for c in str(text or "") if c.isspace() or _drawable(ord(c)))
    return re.sub(r"\s+", " ", text).strip()


def _drawable(code):
    if code < 0x20 or 0x7F <= code < 0xA0:           # control characters
        return False
    if 0x200B <= code <= 0x200F or 0x2028 <= code <= 0x202E or 0x2060 <= code <= 0x206F or code == 0xFEFF:
        return False                                   # zero-width and direction marks
    return _in(_LATIN, code) or _in(_LATIN_EXT, code)


class Face:
    """One typeface made of a latin and a latin-ext file; each character is drawn
    with the file that contains it, so ă, ș and ț come out right."""

    def __init__(self, stem, size, axes=None):
        self.latin = _font(stem, "latin", size, axes)
        self.ext = _font(stem, "latin-ext", size, axes)

    def _pick(self, char):
        return self.latin if _in(_LATIN, ord(char)) else self.ext

    def width(self, text):
        return sum(self._pick(c).getlength(c) for c in text)

    def draw(self, draw, xy, text, fill, spacing=0.0):
        x, y = xy
        for c in text:
            font = self._pick(c)
            draw.text((x, y), c, font=font, fill=fill)
            x += font.getlength(c) + spacing
        return x


@lru_cache(maxsize=64)
def _font(stem, subset, size, axes):
    font = ImageFont.truetype(str(FONT_DIR / f"{stem}-{subset}.ttf"), size)
    if axes:
        font.set_variation_by_axes(list(axes))
    return font


def _face(stem, size, axes=None):
    return Face(stem, size, tuple(axes) if axes else None)


# ------------------------------------------------------------------ versions

def _image_stamp(project):
    """Identifies the screenshot without opening it: name, size and modified time."""
    if not project.image:
        return ""
    try:
        stat = os.stat(project.image.path)
    except (OSError, ValueError):
        return ""
    return f"{project.image.name}|{stat.st_size}|{stat.st_mtime_ns}"


def card_version(project, host):
    parts = (CARD_FORMAT_VERSION, project.title, project.direction, project.status, project.tech_stack,
             host, _image_stamp(project))
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]


def _cache_dir():
    return Path(settings.MEDIA_ROOT) / "share_cards"


def card_path(project, host):
    return _cache_dir() / f"{project.slug}-{card_version(project, host)}.jpg"


# ------------------------------------------------------------------ drawing

def _wrap(face, text, max_width, max_lines):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if face.width(trial) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and face.width(last + "…") > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


def _fit_title(text, max_width, sizes, extra):
    """Largest size from `sizes` at which the title (max 3 lines), the status chip
    and the stack line all fit; the smallest size, cut with an ellipsis, if none does."""
    for size in sizes:
        face = _face("fraunces", size, [36, 460])
        lines = _wrap(face, text, max_width, 99)
        if len(lines) > 3:
            continue
        line_height = int(size * 1.12)
        chip_y = max(200 + len(lines) * line_height + 28, 440)
        if chip_y + 40 + extra <= 556:
            return face, lines, line_height, chip_y
    face = _face("fraunces", sizes[-1], [36, 460])
    lines = _wrap(face, text, max_width, 3)
    line_height = int(sizes[-1] * 1.12)
    return face, lines, line_height, max(200 + len(lines) * line_height + 28, 440)


def _chip(draw, mono, x, y, label, status):
    label = label.upper()
    width = int(mono.width(label) + len(label) * 1.2 + 52)
    x0, y0, x1, y1 = x, y, x + width, y + 40
    if status == "concept":
        for xx in range(x0, x1, 8):
            draw.line([(xx, y0), (min(xx + 4, x1), y0)], fill=BORDER_UI, width=2)
            draw.line([(xx, y1), (min(xx + 4, x1), y1)], fill=BORDER_UI, width=2)
        for yy in range(y0, y1, 8):
            draw.line([(x0, yy), (x0, min(yy + 4, y1))], fill=BORDER_UI, width=2)
            draw.line([(x1, yy), (x1, min(yy + 4, y1))], fill=BORDER_UI, width=2)
    else:
        draw.rectangle((x0, y0, x1, y1), outline=BORDER_UI, width=2)
    cx, cy = x + 20, y + 20
    if status == "demo":
        draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=OK)
    elif status == "produs":
        draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=COBALT)
    elif status == "instrument":
        draw.rectangle((cx - 6, cy - 6, cx + 6, cy + 6), fill=COBALT)
    else:
        draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=INK_2, width=2)
    mono.draw(draw, (x + 38, y + 8), label, INK, spacing=1.2)


def _open_screenshot(project):
    if not project.image:
        return None
    try:
        with Image.open(project.image.path) as raw:
            return ImageOps.exif_transpose(raw).convert("RGB")
    except Exception:  # missing, damaged or unreadable file: draw the card without it
        logger.warning("Share card: cannot read the image of project %s", project.pk)
        return None


def _paste_badge(image, x, y, size):
    """The logo badge (the black tile) before the name. Returns where the name starts.
    If the file is missing the card is simply drawn without it."""
    path = Path(settings.BASE_DIR) / "static" / "website" / "icon-192.png"
    try:
        with Image.open(path) as source:
            badge = source.convert("RGBA").resize((size, size), Image.LANCZOS)
    except (OSError, ValueError):
        return x
    image.paste(badge, (x, y), badge)
    return x + size + 14


def render_card(project, host):
    shot = _open_screenshot(project)
    has_image = shot is not None
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    mono = _face("dm-mono-500", 20)
    mono_small = _face("dm-mono-500", 18)
    body = _face("hanken-grotesk", 26, [400])
    wordmark = _face("fraunces", 38, [36, 500])

    left = 64 if has_image else 80
    text_width = 560 if has_image else 1020
    title = _clean(project.title) or "Proiect"
    stack = _clean(project.tech_stack)

    if not has_image:
        draw.rectangle((0, 0, 20, HEIGHT), fill=COBALT)
    word_x = _paste_badge(image, left, 44, 54)
    x = wordmark.draw(draw, (word_x, 52), "Andreea ", INK)
    wordmark.draw(draw, (x, 52), "Tech", COBALT)
    mono.draw(draw, (left, 156), _clean("PORTOFOLIU · " + project.get_direction_display()).upper(), INK_2, spacing=1.4)

    sizes = [76, 66, 58, 50, 44] if has_image else [96, 84, 74, 64, 56, 48]
    face, lines, line_height, chip_y = _fit_title(title, text_width, sizes, 60 if stack else 0)
    y = 200
    for line in lines:
        face.draw(draw, (left, y), line, INK)
        y += line_height

    _chip(draw, mono, left, chip_y, _clean(project.get_status_display()), project.status)
    if stack:
        while body.width(stack) > text_width and "," in stack:
            stack = stack.rsplit(",", 1)[0].strip()
        body.draw(draw, (left, chip_y + 60), stack, INK_2)
    mono_small.draw(draw, (left, 580), _clean(host).upper(), INK_2, spacing=1.0)

    if has_image:
        x0, x1 = 700, 1136
        frame_width = x1 - x0 - 4
        shot_height = min(round(shot.height * frame_width / shot.width), 420)  # tall shots are cropped from the top
        shot = shot.resize((frame_width, round(shot.height * frame_width / shot.width)), Image.LANCZOS).crop((0, 0, frame_width, shot_height))
        bar = 36 if project.direction == "web" else 0   # browser frame for web projects only
        total = shot_height + bar + 4
        y0 = (HEIGHT - total) // 2
        draw.rectangle((x0, y0, x1, y0 + total), fill=PAPER_2, outline=LINE_STRONG, width=2)
        top = y0 + 2
        if bar:
            draw.rectangle((x0 + 2, top, x1 - 2, top + 34), fill=PAPER_2)
            draw.line([(x0 + 2, top + 34), (x1 - 2, top + 34)], fill=LINE, width=2)
            for i in range(3):
                draw.ellipse((x0 + 18 + i * 20, top + 12, x0 + 28 + i * 20, top + 22), fill=LINE_STRONG)
            top += 36
        image.paste(shot, (x0 + 2, top))
    return image


# ------------------------------------------------------------------ cache

def ensure_card(project, host):
    """Path of the JPEG for this project, drawing it first if it does not exist yet."""
    path = card_path(project, host)
    if path.exists():
        return path
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    image = render_card(project, host)
    handle, tmp_name = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as tmp:
            image.save(tmp, format="JPEG", quality=88, optimize=True)
        os.replace(tmp_name, path)           # atomic: a reader never sees half a file
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    _remove_old_versions(project.slug, keep=path.name)
    return path


def _remove_old_versions(slug, keep):
    pattern = re.compile(rf"^{re.escape(slug)}-[0-9a-f]{{12}}\.jpg$")
    for entry in _cache_dir().iterdir():
        if entry.name != keep and pattern.match(entry.name):
            try:
                entry.unlink()
            except OSError:
                pass

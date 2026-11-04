"""Builds the icon and share-card images from the original logo.

    python scripts/build_brand_assets.py

The original (static/website/brand/logo-original.png) is never modified. Everything
else in static/website/brand/ and the files named below are generated from it, so the
logo can be replaced by running this again. It only needs Pillow, which the project
already uses. It is a developer tool: nothing runs it on the server.

The logo sits on a pure black background, so it is used as a black tile ("badge")
where the site is light, and as the whole image where the space is dark.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "static" / "website" / "brand"
STATIC = ROOT / "static" / "website"
SOURCE = BRAND / "logo-original.png"

# Two crops of the original (left, top, right, bottom), measured on the 1254 px image:
# the letters alone are larger, so they stay readable in small icons; the full mark
# keeps the orbit and the spark for bigger icons.
CROP_LETTERS = (400, 275, 915, 720)
CROP_FULL = (290, 260, 990, 730)


def square(image, box, padding=0.08):
    part = image.crop(box)
    side = int(max(part.size) * (1 + 2 * padding))
    tile = Image.new("RGB", (side, side), (0, 0, 0))
    tile.paste(part, ((side - part.width) // 2, (side - part.height) // 2))
    return tile


def rounded(tile, size, radius=0.22):
    resized = tile.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=int(size * 4 * radius), fill=255)
    resized.putalpha(mask.resize((size, size), Image.LANCZOS))
    return resized


def main():
    original = Image.open(SOURCE).convert("RGB")
    letters = square(original, CROP_LETTERS)
    full = square(original, CROP_FULL)

    # Browser tab and search results
    ico_sizes = [16, 32, 48]
    rounded(letters, 256).save(STATIC / "favicon.ico", sizes=[(s, s) for s in ico_sizes])
    rounded(letters, 32).save(STATIC / "favicon-32.png", optimize=True)
    rounded(letters, 48).save(STATIC / "favicon-48.png", optimize=True)
    rounded(full, 192).save(STATIC / "icon-192.png", optimize=True)
    # iPhone home screen: a plain square, the phone rounds the corners itself
    full.resize((180, 180), Image.LANCZOS).save(STATIC / "apple-touch-icon.png", optimize=True)

    # Menu and footer badge (shown at 40 px, drawn at 2x)
    rounded(letters, 80).save(BRAND / "mark-80.png", optimize=True)

    # Share card: the whole logo on black, 1200x630
    card = Image.new("RGB", (1200, 630), (0, 0, 0))
    logo = original.resize((630, 630), Image.LANCZOS)
    card.paste(logo, ((1200 - 630) // 2, 0))
    card.save(STATIC / "og-default.jpg", quality=86, optimize=True, progressive=True)
    print("done")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check WCAG contrast ratios for the colour pairs the site actually uses.

Run after touching the colours in static/website/tokens.css:

    python scripts/check_contrast.py

It reads the hex values straight out of tokens.css (the light palette from :root and
the dark palette from :root[data-theme="dark"]), so it never drifts out of sync with
what is shipped. Exits non-zero if a pair falls below WCAG AA: 4.5:1 for normal text,
3:1 for large text and for interface parts such as borders and focus rings.

Pairs that use a transparent colour (the hover tint on the call-to-action band) are
not listed: they cannot be checked from two hex values.
"""
import re
import sys
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "website" / "tokens.css"

NORMAL, UI = 4.5, 3.0

# (what it is, foreground token, background token, minimum ratio)
PAIRS = [
    ("Text principal pe fundal", "--ink", "--paper", NORMAL),
    ("Text principal pe fundal secundar", "--ink", "--paper-2", NORMAL),
    ("Text principal pe card", "--ink", "--raised", NORMAL),
    ("Text secundar pe fundal", "--ink-2", "--paper", NORMAL),
    ("Text secundar pe fundal secundar", "--ink-2", "--paper-2", NORMAL),
    ("Text secundar pe card", "--ink-2", "--raised", NORMAL),
    ("Linkuri și accente pe fundal", "--cobalt-text", "--paper", NORMAL),
    ("Linkuri și accente pe fundal secundar", "--cobalt-text", "--paper-2", NORMAL),
    ("Linkuri și accente pe card", "--cobalt-text", "--raised", NORMAL),
    ("Text pe butonul principal", "--on-cobalt", "--cobalt", NORMAL),
    ("Text pe butonul principal la hover", "--paper", "--cobalt-text", NORMAL),
    ("Element ales (filtru, oră): fundal pe ink", "--paper", "--ink", NORMAL),
    ("Confirmare (text verde) pe card", "--ok", "--raised", NORMAL),
    ("Confirmare (text verde) pe fundalul confirmării", "--ok", "--ok-bg", NORMAL),
    ("Text obișnuit pe fundalul confirmării", "--ink", "--ok-bg", NORMAL),
    ("Eroare pe fundal", "--err", "--paper", NORMAL),
    ("Eroare pe card", "--err", "--raised", NORMAL),
    ("Chenar de câmp pe fundal", "--border-ui", "--paper", UI),
    ("Chenar de câmp pe card", "--border-ui", "--raised", UI),
    ("Contur de focus pe fundal", "--cobalt-text", "--paper", UI),
    ("Accent cald (text) pe fundal", "--warm-text", "--paper", NORMAL),
    ("Accent cald (text) pe fundal secundar", "--warm-text", "--paper-2", NORMAL),
    ("Accent cald (text) pe card", "--warm-text", "--raised", NORMAL),
    ("Text pe umplerea caldă", "--on-warm", "--warm", NORMAL),
    ("Text principal pe nuanța de cobalt", "--ink", "--tint", NORMAL),
    ("Text secundar pe nuanța de cobalt", "--ink-2", "--tint", NORMAL),
    ("Linkuri pe nuanța de cobalt", "--cobalt-text", "--tint", NORMAL),
    ("Banda: text pe fundalul benzii", "--on-band", "--band", NORMAL),
    ("Banda: text secundar pe fundalul benzii", "--on-band-2", "--band", NORMAL),
    ("Banda: textul butonului alb", "--band-btn-text", "--on-band", NORMAL),
    ("Banda: textul butonului alb la hover", "--band-btn-text", "--band-btn-hover", NORMAL),
]


def block(css: str, selector: str) -> dict[str, str]:
    """Hex values of the custom properties in the first rule whose selector is exactly `selector`."""
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    match = re.search(pattern, css)
    if not match:
        raise SystemExit(f"Nu găsesc blocul {selector} în tokens.css")
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\b", match.group(1)))


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = relative_luminance(hex_to_rgb(hex_a))
    lum_b = relative_luminance(hex_to_rgb(hex_b))
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def palettes(css: str) -> dict[str, dict[str, str]]:
    light = block(css, ":root")
    dark = {**light, **block(css, ':root[data-theme="dark"]')}   # dark overrides, the rest is shared
    return {"luminoasă": light, "întunecată": dark}


def check(css: str) -> list[tuple[str, str, float, float, str, str, bool]]:
    """One row per theme and pair: (theme, label, ratio, minimum, fg, bg, passed)."""
    rows = []
    for theme, variables in palettes(css).items():
        for label, fg_token, bg_token, minimum in PAIRS:
            fg, bg = variables[fg_token], variables[bg_token]
            ratio = contrast_ratio(fg, bg)
            rows.append((theme, label, ratio, minimum, fg, bg, ratio >= minimum))
    return rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    rows = check(CSS_PATH.read_text(encoding="utf-8"))
    print(f"Verific culorile din {CSS_PATH}\n")
    current = None
    for theme, label, ratio, minimum, fg, bg, passed in rows:
        if theme != current:
            print(f"Tema {theme}")
            current = theme
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: {ratio:.2f}:1 (minim {minimum}:1, {fg} pe {bg})")

    failed = [r for r in rows if not r[-1]]
    print()
    if failed:
        print(f"{len(failed)} combinații pică pragul WCAG AA.")
        return 1
    print(f"Toate cele {len(rows)} combinații trec WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

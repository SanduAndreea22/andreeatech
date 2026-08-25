#!/usr/bin/env python3
"""Check WCAG contrast ratios for the color pairs actually used on the site.

Run after touching the :root palette in static/website/style.css:

    python check_contrast.py

Reads the hex values straight out of style.css, so it never drifts out of
sync with what's actually shipped. Exits non-zero if anything fails its
WCAG AA threshold (4.5:1 for normal text, 3:1 for large text / UI).
"""
import re
import sys
from pathlib import Path

CSS_PATH = Path(__file__).parent / "static" / "website" / "style.css"

# (label, foreground var, background var, "normal" or "large")
# "large" also covers UI components / graphical objects (WCAG 1.4.11), used
# here for solid-fill buttons where the fill itself is the checked pair.
PAIRS = [
    ("Text principal (ink pe paper)", "--ink", "--paper", "normal"),
    ("Text de corp (ink-soft pe paper)", "--ink-soft", "--paper", "normal"),
    ("Eyebrow/etichete (ink-faint pe paper)", "--ink-faint", "--paper", "normal"),
    ("Accent/linkuri (blue-mid pe paper)", "--blue-mid", "--paper", "normal"),
    ("Buton primar (paper pe blue-mid)", "--paper", "--blue-mid", "large"),
]


def parse_root_vars(css_text: str) -> dict[str, str]:
    root_match = re.search(r":root\s*\{([^}]*)\}", css_text)
    if not root_match:
        raise SystemExit("Couldn't find a :root {...} block in style.css")
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", root_match.group(1)))


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


def resolve(token: str, variables: dict[str, str]) -> str:
    return variables[token] if token.startswith("--") else token


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    variables = parse_root_vars(CSS_PATH.read_text(encoding="utf-8"))
    all_passed = True

    print(f"Checking against {CSS_PATH}\n")
    for label, fg_token, bg_token, size in PAIRS:
        fg = resolve(fg_token, variables)
        bg = resolve(bg_token, variables)
        ratio = contrast_ratio(fg, bg)
        threshold = 3.0 if size == "large" else 4.5
        passed = ratio >= threshold
        all_passed &= passed
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {label}: {ratio:.2f}:1 (min {threshold}:1, {fg} pe {bg})")

    print()
    if not all_passed:
        print("Cel puțin o combinație pică pragul WCAG AA.")
        return 1
    print("Toate combinațiile verificate trec WCAG AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The "how much do missed appointments cost you" calculator (/calculator/).

The arithmetic lives here, written once, and the page renders its first state
from it. static/website/site.js repeats the same few lines for live updates, and
a test keeps the two in step (same constant, same results for the starting
numbers). Nothing here is a claim about results: every figure is the visitor's
own input multiplied out, and the formula is shown on the page.
"""

WEEKS_PER_MONTH = 4.33

# Starting values shown in the fields. They are examples, labelled as such on the page.
DEFAULTS = {"per_week": 40, "no_show_pct": 10, "value": 150}


def _round(number):
    # Same rounding as JavaScript's Math.round for non-negative numbers
    # (Python's round() rounds halves to even, which would disagree on x.5).
    return int(number + 0.5)


WEEKS_TEXT = str(WEEKS_PER_MONTH).replace(".", ",")  # "4,33", as written on the page


def format_number(number):
    """1234567 -> '1.234.567' (Romanian thousands separator), always, so the
    server and the script print the same text."""
    return f"{_round(number):,}".replace(",", ".")


def estimate(per_week, no_show_pct, value):
    """Monthly and yearly cost of appointments the client does not show up for.

    Inputs below zero count as zero and the percentage is capped at 100, the
    same clamping the page applies while the visitor types.
    """
    per_week = max(float(per_week), 0.0)
    no_show_pct = min(max(float(no_show_pct), 0.0), 100.0)
    value = max(float(value), 0.0)

    total = per_week * WEEKS_PER_MONTH
    lost = total * no_show_pct / 100
    month = lost * value
    return {
        "total": total,
        "lost": lost,
        "kept": total - lost,
        "lost_pct": no_show_pct,
        "month": month,
        "year": month * 12,
        "one_saved": WEEKS_PER_MONTH * value,
    }


def display(per_week, no_show_pct, value):
    """`estimate()` with every figure already formatted for the page."""
    r = estimate(per_week, no_show_pct, value)
    return {
        "month": format_number(r["month"]),
        "year": format_number(r["year"]),
        "lost": format_number(r["lost"]),
        "total": format_number(r["total"]),
        "kept": format_number(r["kept"]),
        "one_saved": format_number(r["one_saved"]),
        "lost_pct": r["lost_pct"],
        "kept_pct": 100 - r["lost_pct"],
    }

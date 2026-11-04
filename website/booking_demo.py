"""Data for the two-screen booking demo on the home page.

The first state is rendered by the template from these values, and the same
values are handed to static/website/site.js as JSON, so the page and the script
can never disagree about the starting state. Everything here is invented for
the demo and labelled as such on the page: no real client, no real booking.
"""
import json

SLOTS = ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30"]

SERVICES = ["Tuns și coafat", "Manichiură", "Consultație inițială"]

# Pre-filled bookings, shown with the tag "exemplu".
SEED_ROWS = [
    {"time": "10:00", "name": "Ana M.", "service": "Manichiură"},
    {"time": "13:00", "name": "Radu P.", "service": "Consultație inițială"},
]


def context():
    return {
        "demo_slots": SLOTS,
        "demo_services": SERVICES,
        "demo_rows": SEED_ROWS,
        "demo_taken": [row["time"] for row in SEED_ROWS],
        "demo_json": json.dumps({"slots": SLOTS, "rows": SEED_ROWS}, ensure_ascii=False),
    }

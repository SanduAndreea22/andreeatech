"""Single source of truth for the 3 service directions shown on the site.

Each entry maps 1:1 to one of the site's 3 service directions: Web & produse
digitale, Automatizare AI, Design creativ. They are parallel offers, not
escalating tiers of the same service — a visitor picks the direction that
matches what they need.

Prices are starting points ("de la"), not fixed rates: every project gets a
personalised offer after the brief.

The `key` values are stored on existing ContactMessage rows (selected_package),
so they stay unchanged even though the visible names were updated. The
historical names were "Conținut & Prezență Digitală" (continut_digital),
"AI & Automatizare" (ai_automatizare) and "Produse & Sisteme Digitale"
(produse_sisteme).

Used by:
- ContactMessage.PACKAGE_CHOICES (models.py) — so admin/email always show
  the same name+price as the site, without a second hardcoded copy.
- home.html, via the `packages` context variable from views.home.

`slug` is the URL segment of the matching Services page (/servicii/<slug>/).
`price_value` is the plain number backing any price estimate (the € sign and
the "de la" prefix live only in `price`, for display).
"""

PACKAGES = [
    {
        "key": "produse_sisteme",
        "slug": "web",
        "name": "Web & produse digitale",
        "price": "de la €850",
        "price_value": 850,
        "tagline": "Site-uri, sisteme de rezervări și aplicații web la comandă.",
        "features": [
            "Website de prezentare",
            "Sistem de rezervări sau programări",
            "Aplicație web la comandă, în Django și Python",
            "Panou de administrare",
            "Plăți online cu Stripe, acolo unde au sens",
        ],
        "description": "Întregul flux al afacerii tale, construit pe exact ce ai nevoie, nu pe un șablon generic.",
        "duration": "de la 21 de zile",
        "popular": True,
    },
    {
        "key": "ai_automatizare",
        "slug": "ai",
        "name": "Automatizare AI",
        "price": "de la €250",
        "price_value": 250,
        "tagline": "Agenți și automatizări care preiau munca repetitivă.",
        "features": [
            "Asistenți și agenți AI pentru conversații și conținut",
            "Automatizarea sarcinilor repetitive",
            "Confirmări și remindere pentru clienți",
            "Integrări prin API cu serviciile pe care le folosești",
        ],
        "description": "Preiei timpul pierdut pe sarcini repetitive și-l pui înapoi în partea din business care chiar contează.",
        "duration": "de la 14 zile",
        "popular": False,
    },
    {
        "key": "continut_digital",
        "slug": "creativ",
        "name": "Design creativ",
        "price": "de la €150",
        "price_value": 150,
        "tagline": "Identitate vizuală, design pentru social media și campanii.",
        "features": [
            "Identitate vizuală și branding",
            "Design pentru social media",
            "Campanii și materiale vizuale",
            "Direcție creativă",
        ],
        "description": "O prezență online care arată și sună ca brandul tău, nu ca un șablon. Textele sunt incluse în proiect.",
        "duration": "de la 7 zile",
        "popular": False,
    },
]

NOT_SURE_KEY = "not_sure"
NOT_SURE_LABEL = "Nu sunt sigur/ă, hai să discutăm"

# Optional extras that can be added on top of any direction. Used by the
# quick price estimate on the Services page.
ADDONS = [
    {"key": "automation", "name": "Automatizare simplă", "price_value": 15},
    {"key": "agent", "name": "Agent AI", "price_value": 25},
]

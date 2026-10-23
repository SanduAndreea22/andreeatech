"""Single source of truth for the 3 pillar packages shown on the homepage.

Each package maps 1:1 to one of the site's 3 commercial pillars (see the
"Ce fac" section on Acasă): Conținut & Prezență Digitală, AI & Automatizare,
Produse & Sisteme Digitale. These are parallel offers, not escalating tiers
of the same service — a visitor picks the one that matches what they need,
not a bigger/smaller version of the same thing.

Used by:
- ContactMessage.PACKAGE_CHOICES (models.py) — so admin/email always show
  the same name+price as the homepage, without a second hardcoded copy.
- home.html, via the `packages` context variable from views.home — so the
  pricing cards AND the price calculator render name/price/CTA from here
  instead of a second hardcoded copy in the calculator's markup.

`price_value` is the plain number backing the calculator's math (the €
sign and, for produse_sisteme, the "de la" prefix live only in `price`,
for display).
"""

PACKAGES = [
    {
        "key": "continut_digital",
        "name": "Conținut & Prezență Digitală",
        "price": "€150",
        "price_value": 150,
        "tagline": "Conținut care spune clar ce faci — gata de publicat",
        "features": [
            "Postări Instagram și caption-uri",
            "Calendar editorial",
            "Concepte vizuale și materiale de promovare",
            "Website de prezentare (opțional, dacă ai nevoie)",
        ],
        "description": "Ai o prezență online care arată și sună ca lumea, nu doar să existe — conținut gata de publicat, gândit pentru brandul tău, nu generic.",
        "duration": "7 zile",
        "popular": True,
    },
    {
        "key": "ai_automatizare",
        "name": "AI & Automatizare",
        "price": "€250",
        "price_value": 250,
        "tagline": "Fluxuri care îți dau timpul înapoi",
        "features": [
            "Agenți AI pentru generarea și organizarea conținutului",
            "Automatizarea sarcinilor repetitive",
            "Sisteme de lucru personalizate pentru afacerea ta",
        ],
        "description": "Preiei timpul pierdut pe sarcini repetitive și-l pui înapoi în partea din business care chiar contează.",
        "duration": "14 zile",
        "popular": False,
    },
    {
        "key": "produse_sisteme",
        "name": "Produse & Sisteme Digitale",
        "price": "de la €850",
        "price_value": 850,
        "tagline": "Platformă completă, construită pe fluxul tău real",
        "features": [
            "Website-uri și sisteme de rezervări",
            "Platforme și instrumente digitale",
            "Produse proprii și soluții personalizate",
        ],
        "description": "Întregul flux al afacerii tale, construit pe exact ce ai nevoie — nu pe un șablon generic.",
        "duration": "21 zile",
        "popular": False,
    },
]

NOT_SURE_KEY = "not_sure"
NOT_SURE_LABEL = "Nu sunt sigur/ă, hai să discutăm"

"""Single source of truth for the 3 pricing tiers shown on the homepage.

Used by:
- ContactMessage.PACKAGE_CHOICES (models.py) — so admin/email always show
  the same name+price as the homepage, without a second hardcoded copy.
- home.html, via the `packages` context variable from views.home — so the
  pricing cards render name/price/CTA from here instead of literal text.
"""

PACKAGES = [
    {
        "key": "digital_presence",
        "emoji": "🥉",
        "name": "Digital Presence",
        "price": "€150",
        "tagline": "Website simplu — prezența ta online",
        "features": ["Website funcțional", "Prezentare și galerie", "Formular de contact"],
        "description": "Ai un loc unde clienții te găsesc, înțeleg ce faci și te pot contacta — fără să te bazezi doar pe rețele sociale sau recomandări.",
        "duration": "7 zile",
        "popular": False,
    },
    {
        "key": "full_experience",
        "emoji": "🥈",
        "name": "Full Experience",
        "price": "€380",
        "tagline": "Sistem digital personalizat — prezența plus funcționalitate",
        "features": ["Site complet", "Flux automat integrat", "Recenzii clienți", "Dashboard admin"],
        "description": "Clienții pot acționa direct pe site — trimit o cerere sau o programare — iar tu vezi totul într-un singur loc, fără să mai gestionezi manual fiecare pas.",
        "duration": "14 zile",
        "popular": True,
    },
    {
        "key": "premium_system",
        "emoji": "🥇",
        "name": "Premium System",
        "price": "de la €850",
        "tagline": "Sistem digital personalizat — platformă completă",
        "features": ["Platformă completă", "Plăți online", "Sistem și dashboard", "Personalizare în funcție de fluxul business-ului"],
        "description": "Întregul flux — de la cerere la plată — se întâmplă în sistemul tău, construit pe fluxul real al business-ului tău, nu pe un șablon generic.",
        "duration": "21 zile · 5 revizuiri",
        "popular": False,
    },
]

NOT_SURE_KEY = "not_sure"
NOT_SURE_LABEL = "Nu sunt sigur/ă, hai să discutăm"

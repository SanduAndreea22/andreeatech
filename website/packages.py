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
        "name": "Prezență Digitală",
        "price": "€150",
        "tagline": "Website simplu — prezența ta online",
        "features": [
            "Website cu paginile de care ai nevoie (acasă, despre, servicii, galerie)",
            "Poze și descrieri prezentate clar, gata să le vadă clienții",
            "Formular de contact — mesajele ajung direct la tine",
        ],
        "description": "Ai un loc unde clienții te găsesc, înțeleg ce faci și te pot contacta — fără să te bazezi doar pe rețele sociale sau recomandări.",
        "duration": "7 zile",
        "popular": False,
    },
    {
        "key": "full_experience",
        "emoji": "🥈",
        "name": "Experiență Completă",
        "price": "€380",
        "tagline": "Site complet, plus un flux care lucrează pentru tine",
        "features": [
            "Tot ce include Prezență Digitală, plus:",
            "Clienții trimit o cerere sau o programare direct de pe site",
            "Primesc automat o confirmare, fără să scrii tu mesajul",
            "Recenzii de la clienți, afișate direct pe site",
            "Un singur loc unde vezi toate cererile primite",
        ],
        "description": "Clienții pot acționa direct pe site — trimit o cerere sau o programare — iar tu vezi totul într-un singur loc, fără să mai gestionezi manual fiecare pas.",
        "duration": "14 zile",
        "popular": True,
    },
    {
        "key": "premium_system",
        "emoji": "🥇",
        "name": "Sistem Premium",
        "price": "de la €850",
        "tagline": "Platformă completă, construită pe fluxul tău real",
        "features": [
            "Tot ce include Experiență Completă, plus:",
            "Clienții pot plăti online, direct pe site",
            "Sistemul e construit pe pașii reali ai afacerii tale, nu pe un șablon",
            "Panou de control extins, adaptat la ce ai nevoie să vezi și să administrezi",
        ],
        "description": "Întregul flux — de la cerere la plată — se întâmplă în sistemul tău, construit pe fluxul real al business-ului tău, nu pe un șablon generic.",
        "duration": "21 zile",
        "popular": False,
    },
]

NOT_SURE_KEY = "not_sure"
NOT_SURE_LABEL = "Nu sunt sigur/ă, hai să discutăm"

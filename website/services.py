"""Content of the three Services pages (/servicii/web/, /servicii/ai/,
/servicii/creativ/).

Kept in Python, next to packages.py, so the copy lives in one place and the
template stays generic. Prices, durations and names come from packages.py via
`package_key`; nothing here repeats them.
"""
from .models import Project

SERVICES = {
    "web": {
        "direction": Project.DIRECTION_WEB,
        "package_key": "produse_sisteme",
        "meta_description": "Site-uri, sisteme de rezervări și aplicații web la comandă, construite pe felul în care lucrează afacerea ta. Preț de la €850, ofertă personalizată pe cerere.",
        "title": "Site-uri și sisteme de rezervări construite pe felul în care lucrezi tu.",
        "lead": "Pentru restaurante, saloane, clinici, afaceri cu programări și startup-uri care au nevoie de un produs funcțional, nu de un șablon.",
        "benefits": [
            "Website de prezentare",
            "Sistem de rezervări sau programări",
            "Aplicație web făcută la comandă",
            "Panou de administrare pentru tine și echipă",
            "Plăți online cu Stripe, unde au sens",
            "Soluții digitale pentru restaurante și cafenele",
            "Magazin online",
        ],
        "price_factors": "Câte funcții are, cine îl folosește (de exemplu tu și echipa ta), dacă are plăți online sau legături cu alte servicii, dacă designul se face de la zero și cât de repede îl vrei.",
        "cta": "Cere o ofertă pentru web",
        "cta_secondary": "Vezi portofoliul web",
    },
    "ai": {
        "direction": Project.DIRECTION_AI,
        "package_key": "ai_automatizare",
        "meta_description": "Asistenți AI și automatizări care preiau sarcinile repetitive: răspunsuri, confirmări, mesaje de reamintire, conținut. Preț de la €250, ofertă personalizată pe cerere.",
        "title": "Automatizări care preiau sarcinile repetitive, ca să te ocupi tu de clienți.",
        "lead": "Pentru afaceri care pierd ore cu aceleași sarcini în fiecare săptămână și vor să folosească acel timp pentru clienți.",
        "benefits": [
            "Asistenți AI pentru conversații și conținut",
            "Automatizarea sarcinilor repetitive",
            "Automatizare pentru suportul clienților: confirmări și mesaje de reamintire",
            "Legături cu programele pe care le folosești deja (calendar, email, WhatsApp)",
            "Fluxuri de lucru personalizate",
        ],
        "price_factors": "Câți pași are procesul pe care îl automatizăm, cu ce programe trebuie legat și cât de mult trebuie adaptat la felul tău de a lucra.",
        "cta": "Cere o ofertă pentru automatizare",
        "cta_secondary": "Vezi portofoliul de automatizare",
        "has_demo": True,
    },
    "creativ": {
        "direction": Project.DIRECTION_CREATIV,
        "package_key": "continut_digital",
        "meta_description": "Identitate vizuală și branding, design pentru social media, campanii și materiale vizuale, direcție creativă. Preț de la €150, ofertă personalizată pe cerere.",
        "title": "Identitate vizuală și materiale care arată coerent, de la prima postare la campanie.",
        "lead": "Pentru branduri care vor o prezență online care arată și sună ca ele. Este un serviciu creativ separat de partea tehnică: se poate combina cu un site sau un sistem într-un singur proiect, dar nu depinde de ele. Textele sunt incluse în proiecte, nu se vând separat.",
        "benefits": [
            "Identitate vizuală și branding",
            "Design pentru social media",
            "Campanii și materiale vizuale",
            "Direcție creativă",
        ],
        "price_factors": "Volumul de materiale, numărul de formate și dacă brandul are deja o identitate sau pornim de la zero.",
        "cta": "Cere o ofertă creativă",
        "cta_secondary": "Vezi portofoliul creativ",
    },
}

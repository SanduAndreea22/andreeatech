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
        "meta_description": "Site-uri, sisteme de rezervări și aplicații web la comandă, construite pe felul în care lucrează afacerea ta. Preț de la €850, ofertă personalizată după brief.",
        "title": "Site-uri și sisteme de rezervări construite pe felul în care lucrezi tu.",
        "lead": "Pentru restaurante, saloane, clinici, afaceri cu programări și startup-uri care au nevoie de un produs funcțional, nu de un șablon.",
        "benefits": [
            "Website de prezentare",
            "Sistem de rezervări sau programări",
            "Aplicație web la comandă, în Django și Python",
            "Panou de administrare pentru tine și echipă",
            "Plăți online cu Stripe, unde au sens",
            "Soluții digitale pentru restaurante și cafenele",
            "Experiențe de magazin online",
        ],
        "price_factors": "Numărul de funcții și de roluri de utilizator, plățile și integrările externe, dacă design-ul pornește de la zero și termenul de livrare.",
        "cta": "Cere o ofertă pentru web",
        "cta_secondary": "Vezi proiectele web",
    },
    "ai": {
        "direction": Project.DIRECTION_AI,
        "package_key": "ai_automatizare",
        "meta_description": "Agenți AI și automatizări care preiau sarcinile repetitive: răspunsuri, confirmări, remindere, conținut. Preț de la €250, ofertă personalizată după brief.",
        "title": "Automatizări care preiau sarcinile care se repetă, ca tu să te ocupi de clienți.",
        "lead": "Pentru afaceri care pierd ore pe sarcini care se repetă identic și vor ca timpul acela să se întoarcă în relația cu clienții.",
        "benefits": [
            "Asistenți și agenți AI pentru conversații și conținut",
            "Automatizarea sarcinilor repetitive",
            "Automatizare pentru suportul clienților: confirmări și remindere",
            "Integrări prin API cu serviciile pe care le folosești deja",
            "Fluxuri de lucru personalizate",
        ],
        "price_factors": "Numărul de pași din flux, serviciile cu care trebuie conectat și cât de mult trebuie personalizat comportamentul agentului.",
        "cta": "Cere o ofertă pentru automatizare",
        "cta_secondary": "Vezi proiectele de automatizare",
        "has_demo": True,
    },
    "creativ": {
        "direction": Project.DIRECTION_CREATIV,
        "package_key": "continut_digital",
        "meta_description": "Identitate de brand, conținut pentru social media, campanii și materiale de promovare coerente. Preț de la €150, ofertă personalizată după brief.",
        "title": "Identitate și conținut care arată coerent, de la prima postare la materialele de promovare.",
        "lead": "Pentru branduri care vor o prezență online care arată și sună ca ele. Textele sunt incluse în aceste proiecte, nu se vând separat.",
        "benefits": [
            "Concepte de identitate de brand",
            "Conținut pentru social media",
            "Campanii digitale",
            "Materiale de promovare",
            "Direcție creativă",
            "Conținut vizual realizat cu ajutorul AI",
        ],
        "price_factors": "Volumul de materiale, numărul de formate și dacă brandul are deja o identitate sau pornim de la zero.",
        "cta": "Cere o ofertă creativă",
        "cta_secondary": "Vezi proiectele creative",
    },
}

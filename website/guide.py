"""The guide "Ce direcție ți se potrivește?" (/ghid/): three questions, one recommendation.

The questions, the answers' wording and the recommendation rules live here, as
data, in one place. The page hands the same data to static/website/site.js, which
only does generic things with it (show a question, collect an answer, apply the
first rule that matches). `recommend()` below applies the same rules in Python;
it is what the tests use to check every possible combination of answers.

Nothing is stored or sent: this is a guide, not an offer, and the page says so.
Prices and durations are not repeated here; they come from packages.py.
"""
import json

from django.urls import reverse

from .packages import ADDONS, PACKAGES

# Which package each direction points to (the package `key`s are stored on
# existing briefs, so they never change).
PACKAGE_FOR = {"web": "produse_sisteme", "ai": "ai_automatizare", "creativ": "continut_digital"}
AUTOMATION_ONLY_KEY = "automation_only"   # the existing "Doar automatizare / asistent AI (am deja un site)" choice in the brief

_ADDON_PRICE = {a["key"]: a["price_value"] for a in ADDONS}

QUESTIONS = [
    {
        "id": "q1",
        "text": "Ce ar trebui să rezolvăm mai întâi?",
        "options": [
            {"value": "gasit", "label": "Clienții nu mă găsesc sau nu mă iau în serios online", "dir": "web",
             "why": "Ai spus că vrei să fii găsit și luat în serios online. Asta începe cu un site construit pe felul în care lucrezi."},
            {"value": "timp", "label": "Pierd timp cu rezervări, confirmări și mesaje care se repetă", "dir": "ai",
             "why": "Ai spus că pierzi timp cu sarcini care se repetă. Confirmările, mesajele de reamintire și răspunsurile pot fi automatizate."},
            {"value": "unitar", "label": "Nu arăt unitar: logo, postări și materiale diferite peste tot", "dir": "creativ",
             "why": "Ai spus că nu arăți unitar. O identitate vizuală clară pune ordine în logo, postări și materiale."},
            {"value": "app", "label": "Am nevoie de o aplicație sau de un sistem care nu există încă", "dir": "web",
             "why": "Ai spus că ai nevoie de o aplicație sau de un sistem care nu există. Se construiește la comandă, pe ce ai nevoie, nu pe un șablon."},
        ],
    },
    {
        "id": "q2",
        "text": "Ce ai deja?",
        "options": [
            {"value": "nimic", "label": "Încă nimic: nici site, nici identitate vizuală", "short": "nimic încă",
             "why": "Pornești de la zero, așa că putem stabili totul dintr-o dată."},
            {"value": "site", "label": "Un site, dar fără automatizări", "short": "un site",
             "why": "Ai deja un site, deci construim peste el, nu în locul lui."},
            {"value": "brand", "label": "Identitate vizuală (logo, culori), dar fără site", "short": "identitate vizuală, fără site",
             "why": "Ai deja identitatea vizuală, deci pornim de la ea, nu de la zero."},
            {"value": "ambele", "label": "Și site, și identitate vizuală", "short": "site și identitate vizuală",
             "why": "Ai deja și site, și identitate: rămâne partea care le face să lucreze pentru tine."},
        ],
    },
    {
        "id": "q3",
        "text": "Cum ajung clienții la tine acum?",
        "options": [
            {"value": "telefon", "label": "Prin telefon, mesaje sau în persoană", "short": "prin telefon, mesaje sau în persoană",
             "why": "Cererile vin acum prin telefon și mesaje, adică exact locul unde o automatizare are cel mai mult de preluat."},
            {"value": "formular", "label": "Printr-un formular sau printr-un site", "short": "printr-un formular sau un site",
             "why": "Cererile vin deja printr-un formular sau un site, deci ai o bază pe care o putem completa."},
            {"value": "inca", "label": "Încă nu am clienți online", "short": "încă nu am clienți online",
             "why": "Nu ai încă cereri online, așa că pornim de la ce îi face pe clienți să te găsească."},
        ],
    },
]

# First rule whose conditions all match wins. A condition lists the allowed values
# of one field: dir (the direction chosen by question 1), q1, q2 or q3.
KEY_RULES = [
    {
        "if": {"dir": ["ai"], "q2": ["site", "ambele"]},
        "key": AUTOMATION_ONLY_KEY,
        "heading": "Doar automatizare, fără site nou",
        "why": "Fiindcă ai deja un site, recomand doar partea de automatizare, fără un site nou.",
    },
]

ALSO_RULES = [
    {
        "if": {"dir": ["web"], "q3": ["telefon"]},
        "dir": "ai",
        "note": (f"Pentru cererile care vin pe telefon, confirmările și mesajele de reamintire automate se potrivesc bine lângă site. "
                 f"Ca extra la un proiect web, automatizările simple pornesc de la €{_ADDON_PRICE['automation']}, "
                 f"iar un asistent AI de la €{_ADDON_PRICE['agent']}."),
    },
    {
        "if": {"dir": ["web"], "q2": ["nimic"]},
        "dir": "creativ",
        "note": "Dacă nu ai încă identitate vizuală, o pot construi odată cu site-ul, ca serviciu creativ separat.",
    },
    {
        "if": {"dir": ["ai"], "q2": ["nimic", "brand"]},
        "dir": "web",
        "note": "Automatizările funcționează cel mai bine legate de un site sau de un sistem de rezervări.",
    },
    {
        "if": {"dir": ["creativ"], "q2": ["nimic", "brand"]},
        "dir": "web",
        "note": "Un site care leagă materialele între ele vine firesc după identitate.",
    },
]

SUMMARY_TEMPLATE = ("Rezumat din ghid: vreau să rezolv „{q1}”; am deja {q2}; clienții ajung la mine {q3}; "
                    "direcția recomandată: {name} ({price}).")

HOW_IT_WORKS = [
    "Prima întrebare stabilește direcția: site sau aplicație, automatizare ori identitate vizuală.",
    "A doua schimbă recomandarea doar într-un caz: dacă vrei automatizare și ai deja un site, recomand doar automatizarea, fără site nou.",
    "A doua și a treia pot adăuga o direcție care se potrivește și ea, dar nu schimbă prețul direcției principale.",
    "Prețurile și duratele sunt cele din pagina Servicii. Este o orientare, nu o ofertă.",
]


def _option(question_id, value):
    for question in QUESTIONS:
        if question["id"] == question_id:
            for option in question["options"]:
                if option["value"] == value:
                    return option
    raise ValueError(f"Unknown answer {value!r} for {question_id}")


def _matches(condition, context):
    return all(context.get(field) in allowed for field, allowed in condition.items())


def package_for(direction):
    return next(p for p in PACKAGES if p["key"] == PACKAGE_FOR[direction])


def recommend(answers):
    """answers: {"q1": value, "q2": value, "q3": value} -> the recommendation."""
    q1, q2, q3 = (_option(qid, answers[qid]) for qid in ("q1", "q2", "q3"))
    direction = q1["dir"]
    context = {"dir": direction, "q1": q1["value"], "q2": q2["value"], "q3": q3["value"]}
    package = package_for(direction)

    key, heading, q2_why = package["key"], package["name"], q2["why"]
    for rule in KEY_RULES:
        if _matches(rule["if"], context):
            key, heading, q2_why = rule["key"], rule["heading"], rule["why"]
            break

    also = None
    for rule in ALSO_RULES:
        if _matches(rule["if"], context):
            also = {"dir": rule["dir"], "note": rule["note"]}
            break

    summary = SUMMARY_TEMPLATE.format(q1=q1["label"], q2=q2["short"], q3=q3["short"], name=package["name"], price=package["price"])
    return {
        "direction": direction,
        "package": package,
        "key": key,
        "heading": heading,
        "whys": [q1["why"], q2_why, q3["why"]],
        "also": also,
        "summary": summary,
    }


def context():
    """What the page needs: the data for the script, as JSON."""
    brief = reverse("start_project")
    packages = {
        direction: {
            "key": p["key"], "name": p["name"], "price": p["price"], "duration": p["duration"],
            "service_url": reverse("service_detail", args=[p["slug"]]),
        }
        for direction in PACKAGE_FOR
        for p in [package_for(direction)]
    }
    data = {
        "questions": QUESTIONS,
        "packages": packages,
        "key_rules": KEY_RULES,
        "also_rules": ALSO_RULES,
        "summary": SUMMARY_TEMPLATE,
        "brief_url": brief,
        "automation_only_key": AUTOMATION_ONLY_KEY,
    }
    return {"guide_json": json.dumps(data, ensure_ascii=False), "how_it_works": HOW_IT_WORKS}

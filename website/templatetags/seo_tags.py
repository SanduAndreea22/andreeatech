"""Structured data (JSON-LD) for the public pages.

Rule: every value here must be information that is also visible on the page it
appears on. Nothing is invented: no address, phone number, opening hours,
ratings or areas served. Anything not shown on the site is left out.
"""
import json

from django import template
from django.utils.safestring import mark_safe

from website.faq import FAQ_GROUPS

register = template.Library()

ORG_NAME = "Andreea Tech"
EMAIL = "andreea.tech@outlook.com"              # shown in the footer and on Contact
LINKEDIN = "https://www.linkedin.com/in/andreeasandu22"  # linked in the footer


def _origin(request):
    return f"{request.scheme}://{request.get_host()}"


def _script(data):
    # Escape characters that could close the <script> element early.
    payload = (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')


def _organization(request):
    origin = _origin(request)
    return {
        "@type": "Organization",
        "@id": f"{origin}/#organization",
        "name": ORG_NAME,
        "url": f"{origin}/",
        "email": EMAIL,
        "sameAs": [LINKEDIN],
    }


@register.simple_tag(takes_context=True)
def site_jsonld(context):
    request = context["request"]
    origin = _origin(request)
    return _script({
        "@context": "https://schema.org",
        "@graph": [
            _organization(request),
            {
                "@type": "WebSite",
                "@id": f"{origin}/#website",
                "url": f"{origin}/",
                "name": ORG_NAME,
                "inLanguage": "ro",
                "publisher": {"@id": f"{origin}/#organization"},
            },
        ],
    })


@register.simple_tag(takes_context=True)
def service_jsonld(context, package, service):
    """One of the three service directions. Name, description and the
    starting price are exactly what the page shows ("de la €850")."""
    request = context["request"]
    return _script({
        "@context": "https://schema.org",
        "@type": "Service",
        "name": package["name"],
        "description": service["lead"],
        "url": request.build_absolute_uri(request.path),
        "provider": {"@id": f"{_origin(request)}/#organization"},
        "offers": {
            "@type": "Offer",
            "priceSpecification": {
                "@type": "PriceSpecification",
                "minPrice": package["price_value"],
                "priceCurrency": "EUR",
            },
        },
    })


@register.simple_tag(takes_context=True)
def project_jsonld(context, project):
    request = context["request"]
    data = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": project.title,
        "description": project.short_description,
        "url": request.build_absolute_uri(request.path),
        "creator": {"@id": f"{_origin(request)}/#organization"},
    }
    if project.image:
        data["image"] = request.build_absolute_uri(project.image.url)
    return _script(data)


@register.simple_tag
def faq_groups():
    return FAQ_GROUPS


@register.simple_tag
def faq_jsonld():
    questions = [
        {
            "@type": "Question",
            "name": question,
            "acceptedAnswer": {"@type": "Answer", "text": answer},
        }
        for _, _, qs in FAQ_GROUPS
        for question, answer in qs
    ]
    return _script({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": questions})

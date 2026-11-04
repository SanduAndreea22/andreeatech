"""Template tag for the optional availability notice (see SiteSettings)."""
from django import template
from django.db import DatabaseError

from website.models import SiteSettings

register = template.Library()


@register.simple_tag
def availability_text():
    """The text to show, or an empty string when nothing should be shown.

    A missing table (code deployed before `migrate` ran) must never turn into
    a 500 for every page, so a database error simply means "show nothing".
    """
    try:
        settings_row = SiteSettings.objects.only("show_availability", "availability_text").first()
    except DatabaseError:
        return ""
    if settings_row is None or not settings_row.show_availability:
        return ""
    return settings_row.availability_text.strip()

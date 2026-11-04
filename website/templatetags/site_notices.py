"""Template tag for the optional availability notice (see SiteSettings)."""
from django import template
from django.db import DatabaseError

from website.models import Review, SiteSettings

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


@register.simple_tag
def has_approved_reviews():
    """True once at least one review has been approved. Used to show the footer link
    to the reviews page only when there is something to read there. A database
    error (table not there yet) simply means "no"."""
    try:
        return Review.objects.filter(is_approved=True).exists()
    except DatabaseError:
        return False

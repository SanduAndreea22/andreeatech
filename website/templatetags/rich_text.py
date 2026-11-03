from django import template
from django.utils.safestring import mark_safe

from website.sanitize import sanitize_html

register = template.Library()


@register.filter(name="sanitize_html", is_safe=True)
def sanitize_html_filter(value):
    """{{ project.problem|sanitize_html }} replaces |safe for editor HTML:
    the result is marked safe only after it has been cleaned."""
    return mark_safe(sanitize_html(value))

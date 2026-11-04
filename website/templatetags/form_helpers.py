"""Template helper for the public forms: one clear message at the top of a form
that did not go through, so a visitor never lands back on the page wondering
whether anything happened."""
from django import template

register = template.Library()


@register.inclusion_tag("partials/form_errors.html")
def error_summary(form):
    # The hidden honeypot field is not something a visitor can fix, so it is not counted.
    count = len([name for name in form.errors if name != "website" and name != "__all__"])
    return {
        "show": bool(form.errors),
        "count": count,
    }

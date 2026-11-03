"""Sanitising of the rich text of a project (problem, solution, outcome).

Those three fields are written in the admin with CKEditor 4 and shown on the
public project page. The HTML is stored exactly as the editor produced it, and
the editor can only filter in the browser: the server accepts whatever is
posted. So the public page never prints that HTML as it is. It passes through
`sanitize_html()` first, which keeps a short list of harmless formatting and
removes everything else (scripts, event handlers, javascript: links, iframes,
forms, <meta refresh>, <style>, ...). Nothing stored in the database changes.

The allowed list has two parts, so it can be tightened later in one line:

* CORE: what the editor offers today (see CKEDITOR_CONFIGS in settings.py).
* LEGACY: harmless formatting the editor's old default toolbar could produce.
  The restrictive editor configuration was only added on 2026-10-22; content
  saved before that was written with colour, tables, images and raw HTML
  ("Source") available. These tags carry no script or navigation, and keeping
  them means older projects keep their look. Run
  `python manage.py audit_rich_text` to see what your real content uses; if
  nothing needs the LEGACY part, delete it here.
"""
import re
from urllib.parse import urlparse

import nh3

CORE_TAGS = {
    "p", "br", "strong", "em", "u", "ol", "ul", "li", "a",
    "h2", "h3", "h4", "blockquote",
}

LEGACY_TAGS = {
    "b", "i", "s", "strike", "sub", "sup", "code",       # inline formatting
    "h1", "h5", "h6", "pre", "hr", "div", "span",        # blocks and the "Format" list
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "img",                                               # the old "Image" button (this site's own images only)
}

ALLOWED_TAGS = CORE_TAGS | LEGACY_TAGS

# Per tag. Nothing else is kept: no class, id, name, target, on* handlers, ...
ALLOWED_ATTRIBUTES = {
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "span": {"style"},  # the old TextColor / BGColor buttons wrote style on <span>
}

# Only these CSS properties survive inside a style="" attribute.
ALLOWED_STYLE_PROPERTIES = {"color", "background-color"}

# Links (and image sources) must use one of these schemes. Relative URLs such
# as "/contact/" are allowed; javascript:, data:, vbscript:, file: are not.
ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}

# Elements removed together with everything inside them (an unknown tag is
# normally removed but its text kept).
REMOVE_WITH_CONTENT = {
    "script", "style", "iframe", "object", "embed", "noscript", "template",
    "svg", "math", "form", "textarea", "select", "title", "head", "applet",
    "frame", "frameset", "audio", "video", "canvas",
}

# A colour value: #rgb, #rrggbb, #rrggbbaa, a colour name, or rgb()/rgba()/hsl()/hsla()
# with plain numbers. Anything else (url(), expression(), var(), !important, ...) is dropped.
_COLOUR_VALUE = re.compile(
    r"^(#[0-9a-f]{3,8}|[a-z]{3,30}|(?:rgb|hsl)a?\([0-9\s,.%/]{1,40}\))$", re.IGNORECASE
)


def _safe_style(value):
    """Keep only `color` / `background-color` declarations whose value is a plain colour."""
    kept = []
    for declaration in value.split(";"):
        name, sep, val = declaration.partition(":")
        if sep and name.strip().lower() in ALLOWED_STYLE_PROPERTIES and _COLOUR_VALUE.match(val.strip()):
            kept.append(f"{name.strip().lower()}:{val.strip()}")
    return ";".join(kept) or None


def _is_local_url(value):
    """True for a relative URL such as /media/projects/a.png or images/a.png."""
    parts = urlparse(value.strip())
    return not parts.scheme and not parts.netloc and not value.strip().startswith("//")


def _attribute_filter(tag, attribute, value):
    if attribute == "style":
        return _safe_style(value)
    if tag == "img" and attribute == "src":
        # Images may only come from this site. The CSP already refuses images
        # from elsewhere; dropping the address also keeps tracking pixels and
        # data: URIs out of the HTML itself.
        return value if _is_local_url(value) else None
    return value


_CLEANER = nh3.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    url_schemes=ALLOWED_URL_SCHEMES,
    clean_content_tags=REMOVE_WITH_CONTENT,
    filter_style_properties=ALLOWED_STYLE_PROPERTIES,
    attribute_filter=_attribute_filter,
    link_rel="noopener noreferrer",
    strip_comments=True,
)


def sanitize_html(value):
    """Return `value` as safe HTML: the allowed formatting only. Empty and
    None give an empty string."""
    if not value:
        return ""
    return _CLEANER.clean(str(value))

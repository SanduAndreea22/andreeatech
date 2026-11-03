from django.urls import NoReverseMatch, reverse

# Public pages. Every script on the public site is a file served from this
# site (static/website/site.js); the only other <script> blocks are JSON-LD
# data, which browsers do not execute. So scripts need no 'unsafe-inline':
# an injected <script>, an onerror="..." attribute or a javascript: link is
# refused by the browser. Fonts are local, so no outside hosts are listed.
#
# style-src-attr 'unsafe-inline' is still needed because a few templates use
# style="" attributes for one-off spacing; <style> elements are not allowed.
CSP_PUBLIC = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "style-src-attr 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

# Django admin and CKEditor 4 (the rich-text editor in the admin) rely on
# inline scripts and styles, so the admin keeps the same policy it has always
# had. It still blocks remote scripts, frames and objects.
CSP_ADMIN = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


class ContentSecurityPolicyMiddleware:
    """Adds a Content-Security-Policy header to every response: the strict
    CSP_PUBLIC for the public site, and CSP_ADMIN for the admin section.

    The admin is recognised by its URL prefix, read from the URLconf (so it
    keeps working if the admin path is renamed again). If a view sets its own
    header, that one wins.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._admin_prefix = None

    def _admin_path(self):
        if self._admin_prefix is None:
            try:
                self._admin_prefix = reverse("admin:index")
            except NoReverseMatch:
                self._admin_prefix = "/panou-admin/"
        return self._admin_prefix

    def __call__(self, request):
        response = self.get_response(request)
        policy = CSP_ADMIN if request.path.startswith(self._admin_path()) else CSP_PUBLIC
        response.setdefault("Content-Security-Policy", policy)
        return response

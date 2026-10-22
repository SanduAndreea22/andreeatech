CSP_HEADER_VALUE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


class ContentSecurityPolicyMiddleware:
    """Adds a baseline Content-Security-Policy header to every response.

    Templates rely on inline <script> blocks and style="" attributes with
    no nonce infrastructure, so script-src/style-src keep 'unsafe-inline'
    rather than breaking the site — this still blocks the realistic risk
    (a remote script/iframe/object injected through a |safe-rendered
    CKEditor field) without a rewrite of every template.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP_HEADER_VALUE)
        return response

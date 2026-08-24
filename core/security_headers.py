from django.conf import settings


class FrontendSecurityHeadersMiddleware:
    """Apply Makolo's browser security policy without a third-party dependency."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            settings.MAKOLO_CONTENT_SECURITY_POLICY,
        )
        response.setdefault(
            "Permissions-Policy",
            settings.MAKOLO_PERMISSIONS_POLICY,
        )
        # Discovery tiles may be served cross-origin. Send only the Makolo
        # origin on HTTPS cross-origin requests: enough for providers that
        # require a Referer, without leaking paths or query strings.
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

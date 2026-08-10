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
        return response

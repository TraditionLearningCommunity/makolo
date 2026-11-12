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
        if getattr(settings, "CONVERSATIONS_REALTIME_ENABLED", False) and getattr(getattr(request, "user", None), "is_authenticated", False):
            # 'self' does not cover WSS in every browser. Use the validated
            # current host; never enable a blanket wss: CSP source.
            origin = f"{'wss' if request.is_secure() else 'ws'}://{request.get_host()}"
            policy = response["Content-Security-Policy"]
            response["Content-Security-Policy"] = policy.replace("connect-src 'self'", f"connect-src 'self' {origin}")
        response.setdefault(
            "Permissions-Policy",
            settings.MAKOLO_PERMISSIONS_POLICY,
        )
        if getattr(getattr(request, "user", None), "is_authenticated", False) and response.get("Content-Type", "").startswith("text/html"):
            # Voice capture is initiated explicitly in the authenticated global
            # messaging shell. Public documents retain microphone=().
            response["Permissions-Policy"] = response["Permissions-Policy"].replace("microphone=()", "microphone=(self)")
        # Discovery tiles may be served cross-origin. Send only the Makolo
        # origin on HTTPS cross-origin requests: enough for providers that
        # require a Referer, without leaking paths or query strings.
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

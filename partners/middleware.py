from .services import capture_referral_request


class ReferralTrackingMiddleware:
    """Persist a valid ?ref=CODE attribution in the user's session.

    The middleware stores only an opaque visitor UUID and a sanitized referral visit;
    it does not persist IP addresses or full referrer URLs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get("ref", "").strip()
        if code:
            capture_referral_request(request, code)
        return self.get_response(request)

from .models import MarketingLinkVisit
from .services import SESSION_VISIT_ID


class MarketingSessionUserMiddleware:
    """Rattache au compte la visite first-party conservée dans la même session.

    Cela permet qu'un visiteur ouvre un lien /g/... avant de se connecter puis
    finalise son achat après authentification, sans fingerprinting externe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request.user, "is_authenticated", False):
            visit_id = request.session.get(SESSION_VISIT_ID)
            if visit_id:
                MarketingLinkVisit.objects.filter(pk=visit_id, user__isnull=True).update(
                    user=request.user
                )
        return self.get_response(request)

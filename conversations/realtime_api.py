from django.conf import settings
from redis.exceptions import RedisError
from rest_framework import permissions, views
from rest_framework.response import Response

from core.api.privacy import PrivateNoStoreMixin
from .realtime_auth import issue_ticket
from .realtime_limits import within_budget
from .profile_scope import ConversationProfileScopeMixin


class ConversationRealtimeTicketAPIView(ConversationProfileScopeMixin, PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not settings.CONVERSATIONS_REALTIME_ENABLED:
            return Response({"available": False}, status=503)
        try:
            if not within_budget("ticket-budget", str(request.user.pk), maximum=12, seconds=60):
                return Response({"detail": "Réessayez dans une minute."}, status=429)
            return Response({"ticket": issue_ticket(request), "expires_in": 60, "profile_id": str(request.user.pk),
                             "websocket_path": "/ws/v1/conversations/"})
        except (RedisError, OSError):
            return Response({"available": False}, status=503)

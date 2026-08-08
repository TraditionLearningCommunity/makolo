from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics_app.selectors import get_analytics_events
from analytics_app.services import build_event_analytics, build_portfolio_analytics


def _serialize_portfolio(payload):
    data = dict(payload)
    cards = []
    for row in payload["event_cards"]:
        event = row["event"]
        card = dict(row)
        card["event"] = {
            "id": str(event.pk),
            "slug": event.slug,
            "title": event.title,
            "status": event.status,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "capacity": event.capacity,
            "organization": event.organization.name if event.organization_id else None,
        }
        cards.append(card)
    data["event_cards"] = cards
    return data


class AnalyticsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_serialize_portfolio(build_portfolio_analytics(request.user)))


class EventAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(get_analytics_events(request.user), slug=slug)
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError:
            days = 30
        return Response(build_event_analytics(event, request.user, days=days))

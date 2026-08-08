from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics_app.selectors import get_analytics_events
from analytics_app.services import build_event_analytics, build_portfolio_analytics


class AnalyticsOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_portfolio_analytics(request.user))


class EventAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(get_analytics_events(request.user), slug=slug)
        try:
            days = int(request.query_params.get("days", "30"))
        except ValueError:
            days = 30
        return Response(build_event_analytics(event, request.user, days=days))

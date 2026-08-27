from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics_app.event_adapter import build_event_analytics
from analytics_app.growth_contract import build_growth_portfolio, build_organization_growth
from analytics_app.permissions import user_can_view_event_financials
from analytics_app.selectors import (
    get_analytics_events,
    get_growth_organizations,
    get_growth_spends,
)
from analytics_app.services import build_portfolio_analytics
from partners.analytics import build_event_partner_analytics

from .serializers import GrowthSpendSerializer


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


def _serialize_growth_portfolio(payload):
    data = dict(payload)
    cards = []
    for row in payload["cards"]:
        organization = row["organization"]
        card = dict(row)
        card["organization"] = {
            "id": str(organization.pk),
            "slug": organization.slug,
            "name": organization.name,
        }
        cards.append(card)
    data["cards"] = cards
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
        payload = build_event_analytics(event, request.user, days=days)
        payload["partners"] = build_event_partner_analytics(
            event,
            finance_visible=user_can_view_event_financials(request.user, event),
        )
        return Response(payload)


class GrowthOrganizationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_serialize_growth_portfolio(build_growth_portfolio(request.user)))


class OrganizationGrowthAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        try:
            months = int(request.query_params.get("months", "12"))
        except ValueError:
            months = 12
        try:
            cohorts = int(request.query_params.get("cohorts", "6"))
        except ValueError:
            cohorts = 6
        return Response(
            build_organization_growth(
                organization,
                request.user,
                months=months,
                cohort_months=cohorts,
            )
        )


class GrowthSpendListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = get_growth_spends(request.user)
        organization_slug = (request.query_params.get("organization") or "").strip()
        if organization_slug:
            queryset = queryset.filter(organization__slug=organization_slug)
        queryset = queryset[:100]
        return Response(
            GrowthSpendSerializer(queryset, many=True, context={"request": request}).data
        )

    def post(self, request):
        serializer = GrowthSpendSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        spend = serializer.save()
        return Response(
            GrowthSpendSerializer(spend, context={"request": request}).data,
            status=201,
        )


class GrowthSpendDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        spend = get_object_or_404(get_growth_spends(request.user), pk=pk)
        spend.delete()
        return Response(status=204)

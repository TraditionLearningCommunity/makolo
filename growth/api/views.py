from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event
from growth.models import EventFeedback, MarketingLink
from growth.permissions import (
    get_growth_organizations,
    user_can_manage_growth_acquisition,
    user_can_view_private_feedback,
)
from growth.services import activate_crm_preset, available_crm_presets, build_growth_v1_dashboard

from .serializers import EventFeedbackSerializer, MarketingLinkSerializer


def _dashboard_payload(payload):
    data = dict(payload)
    organization = payload["organization"]
    data["organization"] = {
        "id": str(organization.pk),
        "slug": organization.slug,
        "name": organization.name,
    }
    links = []
    for row in payload["marketing_links"]:
        item = dict(row)
        link = row["link"]
        item["link"] = {
            "id": str(link.pk),
            "name": link.name,
            "channel": link.channel,
            "code": link.code,
            "event": {"id": str(link.event_id), "slug": link.event.slug, "title": link.event.title},
            "is_active": link.is_active,
        }
        links.append(item)
    data["marketing_links"] = links
    return data


class GrowthOrganizationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = get_growth_organizations(request.user)[:50]
        return Response(
            [
                {
                    "id": str(org.pk),
                    "slug": org.slug,
                    "name": org.name,
                }
                for org in organizations
            ]
        )


class OrganizationGrowthAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        return Response(_dashboard_payload(build_growth_v1_dashboard(organization, request.user)))


class MarketingLinkListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = get_growth_organizations(request.user)
        queryset = MarketingLink.objects.filter(organization__in=organizations).select_related(
            "organization", "event", "crm_campaign"
        )
        organization_slug = (request.query_params.get("organization") or "").strip()
        if organization_slug:
            queryset = queryset.filter(organization__slug=organization_slug)
        return Response(MarketingLinkSerializer(queryset[:100], many=True, context={"request": request}).data)

    def post(self, request):
        serializer = MarketingLinkSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        link = serializer.save()
        return Response(MarketingLinkSerializer(link, context={"request": request}).data, status=201)


class MarketingLinkToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        link = get_object_or_404(MarketingLink.objects.select_related("organization"), pk=pk)
        if not user_can_manage_growth_acquisition(request.user, link.organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vous ne pouvez pas modifier ce lien marketing.")
        link.is_active = not link.is_active
        link.save(update_fields=["is_active", "updated_at"])
        return Response({"id": str(link.pk), "is_active": link.is_active})


class FeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization_slug = (request.query_params.get("organization") or "").strip()
        if not organization_slug:
            return Response({"detail": "Le paramètre organization est requis."}, status=400)
        organization = get_object_or_404(get_growth_organizations(request.user), slug=organization_slug)
        if not user_can_view_private_feedback(request.user, organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Vous ne pouvez pas lire ce feedback privé.")
        rows = EventFeedback.objects.filter(event__organization=organization).select_related("event", "user")[:200]
        return Response(
            [
                {
                    "id": str(row.pk),
                    "event": {"id": str(row.event_id), "slug": row.event.slug, "title": row.event.title},
                    "rating": row.rating,
                    "comment": row.comment,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        )

    def post(self, request):
        serializer = EventFeedbackSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save()
        return Response(EventFeedbackSerializer(feedback, context={"request": request}).data, status=201)


class CRMPresetsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        rows = []
        for preset in available_crm_presets(organization):
            rows.append(
                {
                    "key": preset["key"],
                    "label": preset["label"],
                    "trigger": preset["trigger"],
                    "event_required": preset["event_required"],
                    "marketing": preset["marketing"],
                }
            )
        return Response(rows)

    def post(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        if not user_can_manage_growth_acquisition(request.user, organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Un rôle Owner, Admin ou Marketing est requis.")
        event = None
        event_id = request.data.get("event_id")
        if event_id:
            event = get_object_or_404(Event.objects.filter(organization=organization), pk=event_id)
        workflow, created = activate_crm_preset(
            organization=organization,
            actor=request.user,
            preset_key=request.data.get("preset_key"),
            event=event,
        )
        return Response(
            {
                "workflow_id": str(workflow.pk),
                "name": workflow.name,
                "created": created,
                "is_active": workflow.is_active,
            },
            status=201 if created else 200,
        )

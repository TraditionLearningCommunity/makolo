from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event
from organizations.models import Organization
from tickets.models import TicketType

from crm.models import AudienceSegment
from crm.selectors import (
    audience_contacts,
    campaign_metrics,
    get_campaigns_visible_to,
    get_contacts_visible_to,
    get_segments_visible_to,
)
from crm.services import (
    cancel_campaign,
    create_campaign,
    create_segment,
    launch_campaign,
    schedule_campaign,
    set_marketing_consent,
    sync_organization_contacts,
)

from .serializers import (
    AudienceSegmentCreateSerializer,
    AudienceSegmentSerializer,
    CommunicationCampaignCreateSerializer,
    CommunicationCampaignSerializer,
    ConsentUpdateSerializer,
    CRMContactSerializer,
)


def _raise_service_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


class ContactListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_contacts_visible_to(request.user)
        organization = request.query_params.get("organization")
        query = (request.query_params.get("q") or "").strip()
        consent = request.query_params.get("consent")
        if organization:
            queryset = queryset.filter(organization_id=organization)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
        if consent:
            queryset = queryset.filter(marketing_consent=consent)
        return Response(CRMContactSerializer(queryset[:500], many=True).data)


class ContactConsentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        serializer = ConsentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            contact = set_marketing_consent(
                contact=contact,
                actor=request.user,
                subscribed=serializer.validated_data["subscribed"],
                source=serializer.validated_data.get("source", ""),
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CRMContactSerializer(contact).data)


class SegmentListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_segments_visible_to(request.user)
        organization = request.query_params.get("organization")
        if organization:
            queryset = queryset.filter(organization_id=organization)
        return Response(AudienceSegmentSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = AudienceSegmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        event_id = data.pop("event_id", None)
        ticket_type_id = data.pop("ticket_type_id", None)
        data["event"] = get_object_or_404(Event, pk=event_id) if event_id else None
        data["ticket_type"] = get_object_or_404(TicketType, pk=ticket_type_id) if ticket_type_id else None
        try:
            segment = create_segment(organization=organization, actor=request.user, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(AudienceSegmentSerializer(segment).data, status=status.HTTP_201_CREATED)


class SegmentPreviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        segment = get_object_or_404(get_segments_visible_to(request.user), pk=pk)
        sync_organization_contacts(segment.organization)
        queryset = audience_contacts(segment)
        return Response(
            {
                "segment_id": str(segment.pk),
                "count": queryset.count(),
                "contacts": CRMContactSerializer(queryset[:100], many=True).data,
            }
        )


class CampaignListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_campaigns_visible_to(request.user)
        organization = request.query_params.get("organization")
        if organization:
            queryset = queryset.filter(organization_id=organization)
        return Response(CommunicationCampaignSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = CommunicationCampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        segment = get_object_or_404(AudienceSegment, pk=data.pop("segment_id"))
        event_id = data.pop("event_id", None)
        scheduled_at = data.pop("scheduled_at", None)
        data["segment"] = segment
        data["event"] = get_object_or_404(Event, pk=event_id) if event_id else None
        try:
            campaign = create_campaign(organization=organization, actor=request.user, **data)
            if scheduled_at:
                schedule_campaign(campaign=campaign, actor=request.user, scheduled_at=scheduled_at)
                campaign.refresh_from_db()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CommunicationCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class CampaignMetricsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        campaign = get_object_or_404(get_campaigns_visible_to(request.user), pk=pk)
        sync_organization_contacts(campaign.organization)
        return Response(
            {
                "campaign": CommunicationCampaignSerializer(campaign).data,
                "preview_count": audience_contacts(campaign.segment).count(),
                "delivery": campaign_metrics(campaign),
            }
        )


class CampaignSendAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        campaign = get_object_or_404(get_campaigns_visible_to(request.user), pk=pk)
        try:
            campaign = launch_campaign(campaign=campaign, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CommunicationCampaignSerializer(campaign).data)


class CampaignCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        campaign = get_object_or_404(get_campaigns_visible_to(request.user), pk=pk)
        try:
            campaign = cancel_campaign(campaign=campaign, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CommunicationCampaignSerializer(campaign).data)

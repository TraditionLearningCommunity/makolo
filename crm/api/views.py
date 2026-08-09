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

from crm.models import AudienceSegment, CampaignTemplate, CRMCustomField, CRMTag
from crm.selectors import (
    audience_contacts,
    campaign_metrics,
    get_campaigns_visible_to,
    get_contacts_visible_to,
    get_segments_visible_to,
)
from crm.services import (
    assign_contact_tag,
    cancel_campaign,
    create_campaign,
    create_campaign_template,
    create_custom_field,
    create_segment,
    create_tag,
    launch_campaign,
    remove_contact_tag,
    schedule_campaign,
    set_contact_custom_value,
    set_marketing_consent,
    sync_organization_contacts,
)

from .serializers import (
    AudienceSegmentCreateSerializer,
    AudienceSegmentSerializer,
    CampaignTemplateCreateSerializer,
    CampaignTemplateSerializer,
    CommunicationCampaignCreateSerializer,
    CommunicationCampaignSerializer,
    ConsentUpdateSerializer,
    ContactCustomFieldValueSerializer,
    ContactTagUpdateSerializer,
    CRMContactSerializer,
    CRMCustomFieldCreateSerializer,
    CRMCustomFieldSerializer,
    CRMTagCreateSerializer,
    CRMTagSerializer,
)


def _raise_service_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


def _organization_visible_to_crm_user(user, organization):
    if user.is_staff:
        return True
    return get_contacts_visible_to(user).filter(organization=organization).exists() or get_segments_visible_to(user).filter(organization=organization).exists() or organization.memberships.filter(user=user, is_active=True, role__in=["owner", "admin", "event_manager", "marketing"]).exists()


class ContactListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_contacts_visible_to(request.user)
        organization = request.query_params.get("organization")
        query = (request.query_params.get("q") or "").strip()
        consent = request.query_params.get("consent")
        tag = request.query_params.get("tag")
        if organization:
            queryset = queryset.filter(organization_id=organization)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
        if consent:
            queryset = queryset.filter(marketing_consent=consent)
        if tag:
            queryset = queryset.filter(tag_links__tag_id=tag)
        return Response(CRMContactSerializer(queryset.distinct()[:500], many=True).data)


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


class ContactTagAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        serializer = ContactTagUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tag = get_object_or_404(CRMTag, pk=serializer.validated_data["tag_id"])
        try:
            assign_contact_tag(contact=contact, tag=tag, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CRMContactSerializer(contact).data)


class ContactTagDeleteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, tag_id):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        tag = get_object_or_404(CRMTag, pk=tag_id, organization=contact.organization)
        try:
            remove_contact_tag(contact=contact, tag=tag, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactCustomFieldAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, field_id):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        field = get_object_or_404(CRMCustomField, pk=field_id, organization=contact.organization, is_active=True)
        serializer = ContactCustomFieldValueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = set_contact_custom_value(
                contact=contact,
                field=field,
                actor=request.user,
                value=serializer.validated_data.get("value"),
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response({"field_id": str(field.pk), "value": record.value})


class TagListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = request.query_params.get("organization")
        queryset = CRMTag.objects.select_related("organization").all()
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        visible_ids = get_contacts_visible_to(request.user).values_list("organization_id", flat=True)
        if not request.user.is_staff:
            queryset = queryset.filter(organization_id__in=visible_ids)
        return Response(CRMTagSerializer(queryset.distinct(), many=True).data)

    def post(self, request):
        serializer = CRMTagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        try:
            tag = create_tag(organization=organization, actor=request.user, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CRMTagSerializer(tag).data, status=status.HTTP_201_CREATED)


class CustomFieldListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = request.query_params.get("organization")
        queryset = CRMCustomField.objects.select_related("organization").all()
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        visible_ids = get_contacts_visible_to(request.user).values_list("organization_id", flat=True)
        if not request.user.is_staff:
            queryset = queryset.filter(organization_id__in=visible_ids)
        return Response(CRMCustomFieldSerializer(queryset.distinct(), many=True).data)

    def post(self, request):
        serializer = CRMCustomFieldCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        try:
            field = create_custom_field(organization=organization, actor=request.user, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CRMCustomFieldSerializer(field).data, status=status.HTTP_201_CREATED)


class TemplateListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = request.query_params.get("organization")
        queryset = CampaignTemplate.objects.select_related("organization").all()
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        if not request.user.is_staff:
            visible_ids = get_campaigns_visible_to(request.user).values_list("organization_id", flat=True)
            member_ids = Organization.objects.filter(memberships__user=request.user, memberships__is_active=True, memberships__role__in=["owner", "admin", "event_manager", "marketing"]).values_list("pk", flat=True)
            queryset = queryset.filter(Q(organization_id__in=visible_ids) | Q(organization_id__in=member_ids))
        return Response(CampaignTemplateSerializer(queryset.distinct(), many=True).data)

    def post(self, request):
        serializer = CampaignTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        try:
            template = create_campaign_template(organization=organization, actor=request.user, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(CampaignTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


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
        tag_ids = data.pop("required_tag_ids", [])
        data["event"] = get_object_or_404(Event, pk=event_id) if event_id else None
        data["ticket_type"] = get_object_or_404(TicketType, pk=ticket_type_id) if ticket_type_id else None
        data["required_tags"] = list(CRMTag.objects.filter(pk__in=tag_ids))
        if len(data["required_tags"]) != len(set(tag_ids)):
            raise ValidationError({"required_tag_ids": "Un ou plusieurs tags sont introuvables."})
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
        return Response({"segment_id": str(segment.pk), "count": queryset.count(), "contacts": CRMContactSerializer(queryset[:100], many=True).data})


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
        template_id = data.pop("template_id", None)
        scheduled_at = data.pop("scheduled_at", None)
        data["segment"] = segment
        data["template"] = get_object_or_404(CampaignTemplate, pk=template_id) if template_id else None
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
        return Response({"campaign": CommunicationCampaignSerializer(campaign).data, "preview_count": audience_contacts(campaign.segment).count(), "delivery": campaign_metrics(campaign)})


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

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from events.models import Event
from organizations.models import Organization
from tickets.models import TicketType

from crm.customer360 import (
    customer_360,
    customer_timeline,
    merge_behavior_filters,
    segment_behavior_filters,
    validate_behavior_filters,
)
from crm.models import AudienceKind, CRMTag
from crm.permissions import user_can_view_customer_360_financials
from crm.selectors import get_contacts_visible_to, get_segments_visible_to
from crm.services import create_segment, sync_organization_contacts

from .serializers import AudienceSegmentSerializer, CRMContactSerializer


class BehavioralSegmentCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    event_id = serializers.UUIDField(required=False, allow_null=True)
    ticket_type_id = serializers.UUIDField(required=False, allow_null=True)
    audience_kind = serializers.ChoiceField(choices=AudienceKind.choices, default=AudienceKind.ALL)
    marketing_consent_only = serializers.BooleanField(default=False)
    city = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    country = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    required_tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    custom_filters = serializers.JSONField(required=False, default=dict)
    behavior_filters = serializers.JSONField(required=False, default=dict)
    is_active = serializers.BooleanField(default=True)

    def validate_behavior_filters(self, value):
        try:
            return validate_behavior_filters(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class Customer360APIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        include_financials = user_can_view_customer_360_financials(
            request.user,
            contact.organization,
        )
        return Response(
            {
                "contact": CRMContactSerializer(contact).data,
                "summary": customer_360(contact, include_financials=include_financials),
                "timeline": customer_timeline(
                    contact,
                    include_financials=include_financials,
                    limit=request.query_params.get("limit", 100),
                ),
                "financials_visible": include_financials,
            }
        )


class BehavioralSegmentListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_segments_visible_to(request.user)
        organization_id = request.query_params.get("organization")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        rows = []
        for segment in queryset:
            behavior = segment_behavior_filters(segment)
            if behavior:
                rows.append(
                    {
                        "segment": AudienceSegmentSerializer(segment).data,
                        "behavior_filters": behavior,
                    }
                )
        return Response(rows)

    def post(self, request):
        serializer = BehavioralSegmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        event_id = data.pop("event_id", None)
        ticket_type_id = data.pop("ticket_type_id", None)
        tag_ids = data.pop("required_tag_ids", [])
        behavior_filters = data.pop("behavior_filters", {})
        data["event"] = get_object_or_404(Event, pk=event_id) if event_id else None
        data["ticket_type"] = get_object_or_404(TicketType, pk=ticket_type_id) if ticket_type_id else None
        tags = list(CRMTag.objects.filter(pk__in=tag_ids))
        if len(tags) != len(set(tag_ids)):
            raise ValidationError({"required_tag_ids": "Un ou plusieurs tags sont introuvables."})
        data["required_tags"] = tags
        data["custom_filters"] = merge_behavior_filters(
            data.get("custom_filters") or {},
            behavior_filters,
        )
        try:
            segment = create_segment(
                organization=organization,
                actor=request.user,
                **data,
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError(exc.messages) from exc

        sync_organization_contacts(organization)
        return Response(
            {
                "segment": AudienceSegmentSerializer(segment).data,
                "behavior_filters": segment_behavior_filters(segment),
            },
            status=status.HTTP_201_CREATED,
        )

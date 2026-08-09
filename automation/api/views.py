from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import AudienceSegment, CampaignTemplate, CRMTag
from crm.permissions import user_can_manage_crm, user_can_view_crm
from events.models import Event
from organizations.models import Organization
from tickets.models import TicketType

from automation.models import CRMWorkflow, CRMWorkflowAction, CRMWorkflowRun

from .serializers import (
    CRMWorkflowActionCreateSerializer,
    CRMWorkflowActionSerializer,
    CRMWorkflowCreateSerializer,
    CRMWorkflowRunSerializer,
    CRMWorkflowSerializer,
)


def _validation_error(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _organization_or_403(user, organization_id, *, manage=False):
    organization = get_object_or_404(Organization, pk=organization_id)
    allowed = user_can_manage_crm(user, organization) if manage else user_can_view_crm(user, organization)
    if not allowed:
        raise PermissionDenied("Vous n’avez pas accès aux automatisations CRM de cette organisation.")
    return organization


def _resolve_workflow_relations(organization, data):
    event_id = data.pop("event_id", None)
    segment_id = data.pop("segment_id", None)
    ticket_type_id = data.pop("ticket_type_id", None)
    data["event"] = get_object_or_404(Event, pk=event_id, organization=organization) if event_id else None
    data["segment"] = get_object_or_404(AudienceSegment, pk=segment_id, organization=organization) if segment_id else None
    data["ticket_type"] = get_object_or_404(TicketType, pk=ticket_type_id, event__organization=organization) if ticket_type_id else None
    return data


class CRMWorkflowListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = request.query_params.get("organization")
        queryset = CRMWorkflow.objects.select_related("organization", "event", "segment", "ticket_type").prefetch_related("actions")
        if organization_id:
            organization = _organization_or_403(request.user, organization_id)
            queryset = queryset.filter(organization=organization)
        elif not request.user.is_staff:
            queryset = queryset.filter(
                organization__memberships__user=request.user,
                organization__memberships__is_active=True,
                organization__memberships__role__in=["owner", "admin", "event_manager", "marketing"],
            ).distinct()
        return Response(CRMWorkflowSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = CRMWorkflowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = _organization_or_403(request.user, data.pop("organization_id"), manage=True)
        data = _resolve_workflow_relations(organization, data)
        workflow = CRMWorkflow(organization=organization, created_by=request.user, **data)
        try:
            workflow.full_clean()
            workflow.save()
        except DjangoValidationError as exc:
            _validation_error(exc)
        return Response(CRMWorkflowSerializer(workflow).data, status=status.HTTP_201_CREATED)


class CRMWorkflowDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _workflow(self, request, pk, *, manage=False):
        workflow = get_object_or_404(
            CRMWorkflow.objects.select_related("organization", "event", "segment", "ticket_type").prefetch_related("actions"),
            pk=pk,
        )
        allowed = user_can_manage_crm(request.user, workflow.organization) if manage else user_can_view_crm(request.user, workflow.organization)
        if not allowed:
            raise PermissionDenied("Vous n’avez pas accès à ce scénario CRM.")
        return workflow

    def get(self, request, pk):
        return Response(CRMWorkflowSerializer(self._workflow(request, pk)).data)

    def patch(self, request, pk):
        workflow = self._workflow(request, pk, manage=True)
        allowed_fields = {
            "name",
            "description",
            "trigger",
            "event_id",
            "segment_id",
            "ticket_type_id",
            "min_order_amount",
            "currency",
            "event_offset_minutes",
            "trigger_grace_minutes",
            "is_active",
        }
        incoming = {key: value for key, value in request.data.items() if key in allowed_fields}
        if not incoming:
            return Response(CRMWorkflowSerializer(workflow).data)
        relation_payload = {}
        for key in ("event_id", "segment_id", "ticket_type_id"):
            if key in incoming:
                relation_payload[key] = incoming.pop(key)
        if relation_payload:
            resolved = _resolve_workflow_relations(workflow.organization, relation_payload)
            for key, value in resolved.items():
                setattr(workflow, key, value)
        for key, value in incoming.items():
            setattr(workflow, key, value)
        try:
            workflow.full_clean()
            workflow.save()
        except DjangoValidationError as exc:
            _validation_error(exc)
        return Response(CRMWorkflowSerializer(workflow).data)


class CRMWorkflowToggleAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous ne pouvez pas activer ou suspendre ce scénario.")
        workflow.is_active = not workflow.is_active
        workflow.save(update_fields=["is_active", "updated_at"])
        return Response(CRMWorkflowSerializer(workflow).data)


class CRMWorkflowActionCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous ne pouvez pas modifier les actions de ce scénario.")
        serializer = CRMWorkflowActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        template_id = data.pop("template_id", None)
        tag_id = data.pop("tag_id", None)
        data["template"] = get_object_or_404(CampaignTemplate, pk=template_id, organization=workflow.organization) if template_id else None
        data["tag"] = get_object_or_404(CRMTag, pk=tag_id, organization=workflow.organization) if tag_id else None
        action = CRMWorkflowAction(workflow=workflow, **data)
        try:
            action.full_clean()
            action.save()
        except DjangoValidationError as exc:
            _validation_error(exc)
        return Response(CRMWorkflowActionSerializer(action).data, status=status.HTTP_201_CREATED)


class CRMWorkflowRunsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_view_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous n’avez pas accès à l’historique de ce scénario.")
        queryset = CRMWorkflowRun.objects.filter(workflow=workflow).select_related("workflow", "contact", "event", "order")[:200]
        return Response(CRMWorkflowRunSerializer(queryset, many=True).data)

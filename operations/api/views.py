from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.permissions import user_can_access_operations
from operations.selectors import (
    get_moderation_cases,
    get_operations_events,
    get_operations_incidents,
    get_operations_organizations,
    get_worker_heartbeats,
)
from operations.services import (
    build_operations_overview,
    change_organization_verification,
    moderate_event,
)

from .serializers import (
    EventModerationSerializer,
    ModerationCaseSerializer,
    OperationsIncidentSerializer,
    OrganizationDecisionSerializer,
    WorkerHeartbeatSerializer,
)


class IsOperationsStaff(BasePermission):
    message = "Le Makolo Operations Center est réservé au staff plateforme."

    def has_permission(self, request, view):
        return user_can_access_operations(request.user)


class OperationsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsOperationsStaff]


class OperationsOverviewAPIView(OperationsAPIView):
    def get(self, request):
        return Response(build_operations_overview(request.user))


class OperationsOrganizationsAPIView(OperationsAPIView):
    def get(self, request):
        queryset = get_operations_organizations(request.user)
        status = (request.query_params.get("status") or "").strip()
        query = (request.query_params.get("q") or "").strip()
        if status:
            queryset = queryset.filter(verification_status=status)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        data = [
            {
                "id": organization.pk,
                "name": organization.name,
                "slug": organization.slug,
                "verification_status": organization.verification_status,
                "public_profile": organization.public_profile,
                "country": organization.country,
                "city": organization.city,
                "event_count": organization.event_count,
                "member_count": organization.member_count,
                "created_at": organization.created_at,
            }
            for organization in queryset[:100]
        ]
        return Response(data)


class OrganizationDecisionAPIView(OperationsAPIView):
    def post(self, request, pk):
        organization = get_object_or_404(get_operations_organizations(request.user), pk=pk)
        serializer = OrganizationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = change_organization_verification(
            organization=organization,
            status=serializer.validated_data["status"],
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(
            {
                "id": organization.pk,
                "name": organization.name,
                "verification_status": organization.verification_status,
            }
        )


class OperationsEventsAPIView(OperationsAPIView):
    def get(self, request):
        queryset = get_operations_events(request.user)
        status = (request.query_params.get("status") or "").strip()
        query = (request.query_params.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(slug__icontains=query)
                | Q(organization__name__icontains=query)
            )
        data = [
            {
                "id": event.pk,
                "title": event.title,
                "slug": event.slug,
                "status": event.status,
                "visibility": event.visibility,
                "organization": event.organization_id,
                "organization_name": event.organization.name if event.organization_id else None,
                "start_at": event.start_at,
                "end_at": event.end_at,
                "created_at": event.created_at,
            }
            for event in queryset[:100]
        ]
        return Response(data)


class EventModerationAPIView(OperationsAPIView):
    def post(self, request, pk):
        event = get_object_or_404(get_operations_events(request.user), pk=pk)
        serializer = EventModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = moderate_event(
            event=event,
            action=serializer.validated_data["action"],
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(
            {
                "id": event.pk,
                "title": event.title,
                "status": event.status,
                "visibility": event.visibility,
                "cancelled_at": event.cancelled_at,
            }
        )


class OperationsIncidentsAPIView(OperationsAPIView):
    def get(self, request):
        queryset = get_operations_incidents(request.user)
        status = (request.query_params.get("status") or "").strip()
        severity = (request.query_params.get("severity") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if severity:
            queryset = queryset.filter(severity=severity)
        return Response(
            OperationsIncidentSerializer(queryset[:100], many=True, context={"request": request}).data
        )

    def post(self, request):
        serializer = OperationsIncidentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()
        return Response(
            OperationsIncidentSerializer(incident, context={"request": request}).data,
            status=201,
        )


class OperationsIncidentDetailAPIView(OperationsAPIView):
    def get(self, request, pk):
        incident = get_object_or_404(get_operations_incidents(request.user), pk=pk)
        return Response(OperationsIncidentSerializer(incident, context={"request": request}).data)

    def patch(self, request, pk):
        incident = get_object_or_404(get_operations_incidents(request.user), pk=pk)
        serializer = OperationsIncidentSerializer(
            incident,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        incident = serializer.save()
        return Response(OperationsIncidentSerializer(incident, context={"request": request}).data)


class ModerationCasesAPIView(OperationsAPIView):
    def get(self, request):
        queryset = get_moderation_cases(request.user)
        status = (request.query_params.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        return Response(ModerationCaseSerializer(queryset[:100], many=True).data)


class WorkerHealthAPIView(OperationsAPIView):
    def get(self, request):
        queryset = get_worker_heartbeats(request.user)
        return Response(WorkerHeartbeatSerializer(queryset, many=True).data)

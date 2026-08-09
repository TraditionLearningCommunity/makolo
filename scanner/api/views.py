from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from scanner.intelligence import event_access_snapshot
from scanner.models import EventAccessGate
from scanner.permissions import user_can_manage_scanner_assignments
from scanner.selectors import (
    get_access_gates_visible_to,
    get_assignments_visible_to,
    get_scan_logs_visible_to,
    get_scannable_events,
)
from scanner.services import scan_ticket
from scanner.throttles import ScannerScanThrottle

from .serializers import (
    EventAccessGateSerializer,
    ScanLogSerializer,
    ScanRequestSerializer,
    ScannerAssignmentSerializer,
    ScannerEventSerializer,
)


class ScannableEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScannerEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self):
        return get_scannable_events(self.request.user).order_by("start_at", "title")


class EventAccessGateViewSet(viewsets.ModelViewSet):
    serializer_class = EventAccessGateSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = get_access_gates_visible_to(self.request.user)
        event_slug = self.request.query_params.get("event")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        return queryset

    def perform_create(self, serializer):
        event = serializer.validated_data["event"]
        if not user_can_manage_scanner_assignments(self.request.user, event):
            raise PermissionDenied("Vous ne pouvez pas créer de porte pour cet événement.")
        gate = serializer.save(created_by=self.request.user)
        try:
            gate.full_clean()
        except DjangoValidationError as exc:
            gate.delete()
            raise ValidationError(exc.message_dict) from exc
        gate.save()

    def perform_update(self, serializer):
        current = self.get_object()
        event = serializer.validated_data.get("event", current.event)
        if not user_can_manage_scanner_assignments(self.request.user, event):
            raise PermissionDenied("Vous ne pouvez pas modifier cette porte.")
        gate = serializer.save()
        try:
            gate.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        gate.save()

    def perform_destroy(self, instance):
        if not user_can_manage_scanner_assignments(self.request.user, instance.event):
            raise PermissionDenied("Vous ne pouvez pas supprimer cette porte.")
        if instance.scan_logs.exists() or instance.assignments.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
            return
        instance.delete()


class ScannerAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = ScannerAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return get_assignments_visible_to(self.request.user)

    def perform_create(self, serializer):
        event = serializer.validated_data["event"]
        if not user_can_manage_scanner_assignments(self.request.user, event):
            raise PermissionDenied("Vous ne pouvez pas affecter un agent à cet événement.")
        assignment = serializer.save(assigned_by=self.request.user)
        try:
            assignment.full_clean()
        except DjangoValidationError as exc:
            assignment.delete()
            raise ValidationError(exc.message_dict) from exc
        assignment.save()

    def perform_update(self, serializer):
        current = self.get_object()
        event = serializer.validated_data.get("event", current.event)
        if not user_can_manage_scanner_assignments(self.request.user, event):
            raise PermissionDenied("Vous ne pouvez pas modifier cette affectation.")
        assignment = serializer.save()
        try:
            assignment.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        assignment.save()

    def perform_destroy(self, instance):
        if not user_can_manage_scanner_assignments(self.request.user, instance.event):
            raise PermissionDenied("Vous ne pouvez pas supprimer cette affectation.")
        if instance.scan_logs.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
            return
        instance.delete()


class ScanLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScanLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_scan_logs_visible_to(self.request.user)
        event_slug = self.request.query_params.get("event")
        result = self.request.query_params.get("result")
        gate_id = self.request.query_params.get("gate")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        if result:
            queryset = queryset.filter(result=result)
        if gate_id:
            queryset = queryset.filter(access_gate_id=gate_id)
        return queryset


class LiveAccessAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        event = get_object_or_404(get_scannable_events(request.user), slug=slug)
        return Response(event_access_snapshot(event))


class ScanAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScannerScanThrottle]

    def post(self, request):
        serializer = ScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            outcome = scan_ticket(
                token=data["token"],
                actor=request.user,
                event=data["event"],
                access_gate=data.get("access_gate"),
                client_reference=data.get("client_reference", ""),
                gate=data.get("gate", ""),
                metadata={
                    "source": "api",
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:250],
                },
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError(exc.messages) from exc

        response_data = {
            "accepted": outcome.accepted,
            "result": outcome.result,
            "message": outcome.message,
            "scan": ScanLogSerializer(outcome.log, context={"request": request}).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

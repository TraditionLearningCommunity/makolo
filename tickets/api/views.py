from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from events.permissions import user_can_manage_event
from tickets.models import TicketOrder, TicketTransfer, TicketWaitlistEntry
from tickets.permissions import IsTicketOrganizer, IsTicketTypeOwnerOrAdmin
from tickets.selectors import (
    get_orders_visible_to,
    get_ticket_transfers_visible_to,
    get_ticket_types_visible_to,
    get_tickets_visible_to,
    get_waitlist_entries_visible_to,
)
from tickets.services import (
    accept_ticket_transfer,
    accept_waitlist_offer,
    cancel_order,
    cancel_ticket_transfer,
    decline_ticket_transfer,
    leave_waitlist,
)

from .serializers import (
    TicketOrderCreateSerializer,
    TicketOrderSerializer,
    TicketSerializer,
    TicketTransferCreateSerializer,
    TicketTransferSerializer,
    TicketTypeSerializer,
    TicketWaitlistCreateSerializer,
    TicketWaitlistSerializer,
)


class TicketTypeViewSet(viewsets.ModelViewSet):
    serializer_class = TicketTypeSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = get_ticket_types_visible_to(self.request.user)
        event_slug = self.request.query_params.get("event")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        return queryset.order_by("event__start_at", "price", "name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            classes = [permissions.AllowAny]
        elif self.action == "create":
            classes = [IsTicketOrganizer]
        else:
            classes = [IsTicketTypeOwnerOrAdmin]
        return [permission() for permission in classes]

    def perform_create(self, serializer):
        ticket_type = serializer.save()
        if not user_can_manage_event(self.request.user, ticket_type.event):
            ticket_type.delete()
            raise DRFPermissionDenied(
                "Vous ne pouvez pas gérer les billets de cet événement."
            )
        try:
            ticket_type.full_clean()
        except DjangoValidationError as exc:
            ticket_type.delete()
            raise ValidationError(exc.message_dict) from exc
        ticket_type.save()

    def perform_update(self, serializer):
        ticket_type = serializer.save()
        try:
            ticket_type.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        ticket_type.save()

    def perform_destroy(self, instance):
        if instance.reserved_quantity or instance.issued_quantity:
            raise ValidationError(
                "Un type de billet déjà réservé ou émis ne peut pas être supprimé."
            )
        instance.delete()


class TicketOrderViewSet(viewsets.ModelViewSet):
    queryset = TicketOrder.objects.none()
    http_method_names = ["get", "post", "head", "options"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return get_orders_visible_to(self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return TicketOrderCreateSerializer
        return TicketOrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(
            TicketOrderSerializer(order, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _transition(self, request, service):
        order = self.get_object()
        try:
            service(order=order, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        order.refresh_from_db()
        return Response(
            TicketOrderSerializer(order, context={"request": request}).data
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, cancel_order)


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_tickets_visible_to(self.request.user)
        event_slug = self.request.query_params.get("event")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        return queryset


class TicketWaitlistViewSet(viewsets.ModelViewSet):
    queryset = TicketWaitlistEntry.objects.none()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return get_waitlist_entries_visible_to(self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return TicketWaitlistCreateSerializer
        return TicketWaitlistSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        return Response(
            TicketWaitlistSerializer(entry, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        entry = self.get_object()
        try:
            leave_waitlist(entry=entry, user=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        entry.refresh_from_db()
        return Response(TicketWaitlistSerializer(entry).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        entry = self.get_object()
        try:
            order = accept_waitlist_offer(entry=entry, user=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        order.refresh_from_db()
        return Response(TicketOrderSerializer(order, context={"request": request}).data)


class TicketTransferViewSet(viewsets.ModelViewSet):
    queryset = TicketTransfer.objects.none()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return get_ticket_transfers_visible_to(self.request.user).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return TicketTransferCreateSerializer
        return TicketTransferSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transfer = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        return Response(
            TicketTransferSerializer(transfer, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _transition(self, request, service, actor_keyword):
        transfer = self.get_object()
        try:
            service(transfer=transfer, **{actor_keyword: request.user})
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except PermissionDenied as exc:
            raise DRFPermissionDenied(str(exc)) from exc
        transfer.refresh_from_db()
        return Response(TicketTransferSerializer(transfer, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._transition(request, accept_ticket_transfer, "recipient")

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._transition(request, decline_ticket_transfer, "recipient")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, cancel_ticket_transfer, "sender")

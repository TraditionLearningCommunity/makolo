from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from automation.services import ensure_policy
from events.models import EventCategory, EventStatus, EventVenue
from events.permissions import IsEventOrganizer, IsEventOwnerOrAdmin
from events.selectors import get_events_visible_to
from events.services import cancel_event, complete_event, create_event, publish_event, reopen_event, update_event
from organizations.services import ensure_personal_organization

from .serializers import (
    EventCategorySerializer,
    EventDetailSerializer,
    EventListSerializer,
    EventVenueSerializer,
    EventWriteSerializer,
)


class EventCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EventCategory.objects.filter(is_active=True).order_by("name")
    serializer_class = EventCategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


class EventVenueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EventVenue.objects.select_related("place").filter(is_active=True).order_by("name")
    serializer_class = EventVenueSerializer
    permission_classes = [permissions.AllowAny]


class EventViewSet(viewsets.ModelViewSet):
    lookup_field = "slug"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return get_events_visible_to(
            self.request.user,
            for_detail=self.action in {"retrieve", "partial_update", "destroy", "publish", "cancel", "complete", "reopen"},
        )

    def get_serializer_class(self):
        if self.action == "list":
            return EventListSerializer
        if self.action in {"create", "partial_update"}:
            return EventWriteSerializer
        return EventDetailSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            classes = [permissions.AllowAny]
        elif self.action == "create":
            classes = [IsEventOrganizer]
        else:
            classes = [IsEventOwnerOrAdmin]
        return [permission() for permission in classes]

    def perform_create(self, serializer):
        values = dict(serializer.validated_data)
        organization = values.pop("organization", None) or ensure_personal_organization(self.request.user)
        event = create_event(actor=self.request.user, organization=organization, **values)
        ensure_policy(event)
        serializer.instance = event

    def perform_update(self, serializer):
        values = dict(serializer.validated_data)
        organization = values.pop("organization", None)
        event = update_event(
            event=serializer.instance,
            actor=self.request.user,
            organization=organization,
            **values,
        )
        serializer.instance = event

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        self.check_object_permissions(request, event)
        if event.status == EventStatus.PUBLISHED:
            raise ValidationError("Un événement publié doit être annulé avant sa suppression.")
        return super().destroy(request, *args, **kwargs)

    def _transition(self, request, service):
        event = self.get_object()
        self.check_object_permissions(request, event)
        try:
            service(event=event, actor=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(
            EventDetailSerializer(event, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, slug=None):
        return self._transition(request, publish_event)

    @action(detail=True, methods=["post"])
    def cancel(self, request, slug=None):
        return self._transition(request, cancel_event)

    @action(detail=True, methods=["post"])
    def complete(self, request, slug=None):
        return self._transition(request, complete_event)

    @action(detail=True, methods=["post"])
    def reopen(self, request, slug=None):
        return self._transition(request, reopen_event)

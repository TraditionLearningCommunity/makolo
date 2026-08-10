from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions

from events.selectors import get_public_discoverable_events
from tickets.selectors import get_public_ticket_types_for_event

from .participant_serializers import (
    DiscoverEventQuerySerializer,
    ParticipantEventDetailSerializer,
    ParticipantEventListSerializer,
    ParticipantTicketTypeSerializer,
)


class ParticipantEventDiscoverAPIView(generics.ListAPIView):
    """Public event feed for participant/mobile clients only."""

    serializer_class = ParticipantEventListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        params = DiscoverEventQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        filters = params.validated_data

        queryset = get_public_discoverable_events(upcoming_only=True)
        search = filters.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(short_description__icontains=search)
                | Q(description__icontains=search)
                | Q(venue__city__icontains=search)
                | Q(organization__name__icontains=search)
            )
        category = filters.get("category", "").strip()
        if category:
            queryset = queryset.filter(category__slug=category)
        city = filters.get("city", "").strip()
        if city:
            queryset = queryset.filter(venue__city__iexact=city)
        if filters.get("date_min"):
            queryset = queryset.filter(start_at__date__gte=filters["date_min"])
        if filters.get("date_max"):
            queryset = queryset.filter(start_at__date__lte=filters["date_max"])
        return queryset.order_by(filters.get("ordering", "start_at"), "title")


class ParticipantEventDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ParticipantEventDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return get_public_discoverable_events(upcoming_only=False)


class ParticipantTicketTypeListAPIView(generics.ListAPIView):
    serializer_class = ParticipantTicketTypeSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        event = get_object_or_404(
            get_public_discoverable_events(upcoming_only=False),
            slug=self.kwargs["slug"],
        )
        return get_public_ticket_types_for_event(event)

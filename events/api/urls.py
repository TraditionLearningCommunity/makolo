from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .participant_views import (
    ParticipantEventDetailAPIView,
    ParticipantEventDiscoverAPIView,
    ParticipantTicketTypeListAPIView,
)
from .views import EventCategoryViewSet, EventVenueViewSet, EventViewSet


router = DefaultRouter()
router.register("", EventViewSet, basename="events")

category_list = EventCategoryViewSet.as_view({"get": "list"})
category_detail = EventCategoryViewSet.as_view({"get": "retrieve"})
venue_list = EventVenueViewSet.as_view({"get": "list"})
venue_detail = EventVenueViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("discover/", ParticipantEventDiscoverAPIView.as_view(), name="participant-event-discover"),
    path(
        "discover/<slug:slug>/",
        ParticipantEventDetailAPIView.as_view(),
        name="participant-event-detail",
    ),
    path(
        "<slug:slug>/ticket-types/",
        ParticipantTicketTypeListAPIView.as_view(),
        name="participant-ticket-type-list",
    ),
    path("categories/", category_list, name="event-category-list"),
    path(
        "categories/<slug:slug>/",
        category_detail,
        name="event-category-detail",
    ),
    path("venues/", venue_list, name="event-venue-list"),
    path("venues/<uuid:pk>/", venue_detail, name="event-venue-detail"),
    path("", include(router.urls)),
]

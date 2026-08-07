from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EventCategoryViewSet, EventVenueViewSet, EventViewSet


router = DefaultRouter()
router.register("", EventViewSet, basename="events")

category_list = EventCategoryViewSet.as_view({"get": "list"})
category_detail = EventCategoryViewSet.as_view({"get": "retrieve"})
venue_list = EventVenueViewSet.as_view({"get": "list"})
venue_detail = EventVenueViewSet.as_view({"get": "retrieve"})

urlpatterns = [
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

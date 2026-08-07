from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EventCategoryViewSet, EventVenueViewSet, EventViewSet


router = DefaultRouter()
router.register("categories", EventCategoryViewSet, basename="event-categories")
router.register("venues", EventVenueViewSet, basename="event-venues")
router.register("events", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (
    ScanAPIView,
    ScanLogViewSet,
    ScannableEventViewSet,
    ScannerAssignmentViewSet,
)


router = DefaultRouter()
router.register("events", ScannableEventViewSet, basename="scanner-event")
router.register("assignments", ScannerAssignmentViewSet, basename="scanner-assignment")
router.register("logs", ScanLogViewSet, basename="scanner-log")

urlpatterns = [
    path("scan/", ScanAPIView.as_view(), name="scan"),
    path("", include(router.urls)),
]

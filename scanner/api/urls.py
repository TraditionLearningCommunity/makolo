from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (
    EventAccessGateViewSet,
    LiveAccessAPIView,
    ScanAPIView,
    ScanLogViewSet,
    ScannableEventViewSet,
    ScannerAssignmentViewSet,
)


router = DefaultRouter()
router.register("events", ScannableEventViewSet, basename="scanner-event")
router.register("gates", EventAccessGateViewSet, basename="scanner-gate")
router.register("assignments", ScannerAssignmentViewSet, basename="scanner-assignment")
router.register("logs", ScanLogViewSet, basename="scanner-log")

urlpatterns = [
    path("scan/", ScanAPIView.as_view(), name="scan"),
    path("events/<slug:slug>/live/", LiveAccessAPIView.as_view(), name="live-access"),
    path("", include(router.urls)),
]

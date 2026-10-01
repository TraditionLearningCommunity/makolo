from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .context_views import ScannerOccurrenceContextAPIView
from .mobile_views import CurrentScannerAssignmentListAPIView
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
    path(
        "occurrences/<uuid:occurrence_id>/context/",
        ScannerOccurrenceContextAPIView.as_view(),
        name="occurrence-context",
    ),
    path(
        "assignments/current/",
        CurrentScannerAssignmentListAPIView.as_view(),
        name="current-assignments",
    ),
    path("events/<slug:slug>/live/", LiveAccessAPIView.as_view(), name="live-access"),
    path("", include(router.urls)),
]

from django.urls import path

from .views import (
    AccessGateCreateView,
    AccessGateListView,
    AccessGateUpdateView,
    LiveAccessDashboardView,
    LiveAccessSnapshotView,
    ScanLogListView,
    ScannerAssignmentCreateView,
    ScannerAssignmentListView,
    ScannerAssignmentUpdateView,
    ScannerEventConsoleView,
    ScannerHomeView,
    ScannerWebScanView,
)


app_name = "scanner"

urlpatterns = [
    path("", ScannerHomeView.as_view(), name="home"),
    path("logs/", ScanLogListView.as_view(), name="logs"),
    path("gates/", AccessGateListView.as_view(), name="gates"),
    path("gates/new/", AccessGateCreateView.as_view(), name="gate-create"),
    path("gates/<uuid:pk>/edit/", AccessGateUpdateView.as_view(), name="gate-edit"),
    path("assignments/", ScannerAssignmentListView.as_view(), name="assignments"),
    path(
        "assignments/new/",
        ScannerAssignmentCreateView.as_view(),
        name="assignment-create",
    ),
    path(
        "assignments/<uuid:pk>/edit/",
        ScannerAssignmentUpdateView.as_view(),
        name="assignment-edit",
    ),
    path("event/<slug:slug>/", ScannerEventConsoleView.as_view(), name="console"),
    path("event/<slug:slug>/scan/", ScannerWebScanView.as_view(), name="scan"),
    path("event/<slug:slug>/live/", LiveAccessDashboardView.as_view(), name="live-access"),
    path("event/<slug:slug>/live.json", LiveAccessSnapshotView.as_view(), name="live-access-json"),
]

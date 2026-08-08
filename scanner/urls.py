from django.urls import path

from .views import (
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
]

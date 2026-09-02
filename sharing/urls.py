from django.urls import path

from .views import (
    ActivityShareCreateView,
    OccurrenceShareCreateView,
    OpportunityShareCreateView,
    ShareActionView,
    ShareLandingView,
    ShareQRView,
)


app_name = "sharing"

urlpatterns = [
    path("s/<slug:token>/", ShareLandingView.as_view(), name="landing"),
    path("s/<slug:token>/go/", ShareActionView.as_view(), name="action"),
    path("s/<slug:token>/qr.png", ShareQRView.as_view(), name="qr"),
    path(
        "sharing/create/activity/<uuid:activity_id>/",
        ActivityShareCreateView.as_view(),
        name="create-activity",
    ),
    path(
        "sharing/create/occurrence/<uuid:occurrence_id>/",
        OccurrenceShareCreateView.as_view(),
        name="create-occurrence",
    ),
    path(
        "sharing/create/opportunity/<uuid:opportunity_id>/",
        OpportunityShareCreateView.as_view(),
        name="create-opportunity",
    ),
]

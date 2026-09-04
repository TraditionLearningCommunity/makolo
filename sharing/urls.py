from django.urls import path

from .document_views import (
    InboundCaptureAbsorbView,
    InboundCaptureCreateView,
    InboundCaptureDetailView,
    InboundCaptureDiscardView,
)
from .passport_views import MyPassportView, ProfilePassportView, SpacePassportView
from .views import (
    ActivityShareCreateView,
    JourneyReuseShareView,
    OccurrenceShareCreateView,
    OpportunityShareCreateView,
    ProfileSearchView,
    ShareActionView,
    ShareDeliveryAcceptView,
    ShareDeliveryDeclineView,
    ShareDeliveryGoView,
    ShareDeliveryLandingView,
    ShareLandingView,
    ShareQRView,
)


app_name = "sharing"

urlpatterns = [
    path("passport/me/", MyPassportView.as_view(), name="passport-me"),
    path("passport/profile/<uuid:profile_id>/", ProfilePassportView.as_view(), name="passport-profile"),
    path("passport/spaces/<slug:slug>/", SpacePassportView.as_view(), name="passport-space"),
    path("s/<slug:token>/", ShareLandingView.as_view(), name="landing"),
    path("s/<slug:token>/go/", ShareActionView.as_view(), name="action"),
    path("s/<slug:token>/qr.png", ShareQRView.as_view(), name="qr"),
    path("sharing/people/search/", ProfileSearchView.as_view(), name="profile-search"),
    path("sharing/import/", InboundCaptureCreateView.as_view(), name="inbound-create"),
    path("sharing/import/<uuid:capture_id>/", InboundCaptureDetailView.as_view(), name="inbound-detail"),
    path("sharing/import/<uuid:capture_id>/absorb/", InboundCaptureAbsorbView.as_view(), name="inbound-absorb"),
    path("sharing/import/<uuid:capture_id>/discard/", InboundCaptureDiscardView.as_view(), name="inbound-discard"),
    path(
        "sharing/journey/<uuid:journey_id>/reuse/",
        JourneyReuseShareView.as_view(),
        name="journey-reuse",
    ),
    path("shares/<uuid:delivery_id>/", ShareDeliveryLandingView.as_view(), name="delivery"),
    path("shares/<uuid:delivery_id>/go/", ShareDeliveryGoView.as_view(), name="delivery-go"),
    path("shares/<uuid:delivery_id>/accept/", ShareDeliveryAcceptView.as_view(), name="delivery-accept"),
    path("shares/<uuid:delivery_id>/decline/", ShareDeliveryDeclineView.as_view(), name="delivery-decline"),
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

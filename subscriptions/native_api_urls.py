from .space_native_api_views import (
    SpaceSubscriptionAPIView,
    SpaceSubscriptionAddonRemoveAPIView,
    SpaceSubscriptionHistoryAPIView,
    SpaceSubscriptionObligationsAPIView,
    SpaceSubscriptionPlanAPIView,
    SpaceSubscriptionTransitionAPIView,
)
from django.urls import path

from .native_api_views import (
    PersonalSubscriptionAddonRemoveAPIView,
    PersonalSubscriptionAPIView,
    PersonalSubscriptionHistoryAPIView,
    PersonalSubscriptionObligationsAPIView,
    PersonalSubscriptionPlanAPIView,
    PersonalSubscriptionTransitionAPIView,
)

app_name = "subscriptions_native"
urlpatterns = [
    path("me/", PersonalSubscriptionAPIView.as_view(), name="me"),
    path("me/obligations/", PersonalSubscriptionObligationsAPIView.as_view(), name="obligations"),
    path("me/transitions/", PersonalSubscriptionHistoryAPIView.as_view(), name="history"),
    path("me/plans/<uuid:plan_version_id>/", PersonalSubscriptionPlanAPIView.as_view(), name="plan"),
    path("me/addons/<uuid:item_id>/remove/", PersonalSubscriptionAddonRemoveAPIView.as_view(), name="addon-remove"),
    path("me/transitions/<uuid:transition_id>/<str:operation>/", PersonalSubscriptionTransitionAPIView.as_view(), name="transition"),
]

urlpatterns += [
    path("spaces/<slug:slug>/", SpaceSubscriptionAPIView.as_view(), name="space"),
    path("spaces/<slug:slug>/obligations/", SpaceSubscriptionObligationsAPIView.as_view(), name="space-obligations"),
    path("spaces/<slug:slug>/transitions/", SpaceSubscriptionHistoryAPIView.as_view(), name="space-history"),
    path("spaces/<slug:slug>/plans/<uuid:plan_version_id>/", SpaceSubscriptionPlanAPIView.as_view(), name="space-plan"),
    path("spaces/<slug:slug>/addons/<uuid:item_id>/remove/", SpaceSubscriptionAddonRemoveAPIView.as_view(), name="space-addon-remove"),
    path("spaces/<slug:slug>/transitions/<uuid:transition_id>/<str:operation>/", SpaceSubscriptionTransitionAPIView.as_view(), name="space-transition"),
]

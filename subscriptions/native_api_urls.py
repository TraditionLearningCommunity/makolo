from django.urls import path

from .native_api_views import (
    PersonalSubscriptionAddonRemoveAPIView,
    PersonalSubscriptionAPIView,
    PersonalSubscriptionObligationsAPIView,
    PersonalSubscriptionPlanAPIView,
    PersonalSubscriptionTransitionAPIView,
)

app_name = "subscriptions_native"
urlpatterns = [
    path("me/", PersonalSubscriptionAPIView.as_view(), name="me"),
    path("me/obligations/", PersonalSubscriptionObligationsAPIView.as_view(), name="obligations"),
    path("me/plans/<uuid:plan_version_id>/", PersonalSubscriptionPlanAPIView.as_view(), name="plan"),
    path("me/addons/<uuid:item_id>/remove/", PersonalSubscriptionAddonRemoveAPIView.as_view(), name="addon-remove"),
    path("me/transitions/<uuid:transition_id>/<str:operation>/", PersonalSubscriptionTransitionAPIView.as_view(), name="transition"),
]

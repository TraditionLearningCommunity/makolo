from django.urls import path

from .web_views import (
    ProfileAddonRemovePreviewView,
    ProfileAddonRemoveView,
    ProfileSubscriptionChangeView,
    ProfileSubscriptionPreviewView,
    ProfileSubscriptionView,
    ProfileTransitionCancelView,
    ProfileTransitionCompleteView,
)


app_name = "subscriptions"

urlpatterns = [
    path("", ProfileSubscriptionView.as_view(), name="home"),
    path("preview/<uuid:plan_version_id>/", ProfileSubscriptionPreviewView.as_view(), name="preview"),
    path("change/<uuid:plan_version_id>/", ProfileSubscriptionChangeView.as_view(), name="change"),
    path("addon/<uuid:item_id>/remove/preview/", ProfileAddonRemovePreviewView.as_view(), name="addon-remove-preview"),
    path("addon/<uuid:item_id>/remove/", ProfileAddonRemoveView.as_view(), name="addon-remove"),
    path("transition/<uuid:transition_id>/cancel/", ProfileTransitionCancelView.as_view(), name="transition-cancel"),
    path("transition/<uuid:transition_id>/complete/", ProfileTransitionCompleteView.as_view(), name="transition-complete"),
]

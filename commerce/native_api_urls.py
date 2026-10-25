from django.urls import path

from .native_checkout_api import PersonalCommerceCheckoutAPIView
from .native_activity_checkout_api import ActivityCommerceCheckoutAPIView

app_name = "commerce_api"

urlpatterns = [
    path("activities/<uuid:activity_id>/checkout/", ActivityCommerceCheckoutAPIView.as_view(), name="activity-checkout"),
    path("journeys/<uuid:journey_id>/checkout/", PersonalCommerceCheckoutAPIView.as_view(), name="journey-checkout"),
]

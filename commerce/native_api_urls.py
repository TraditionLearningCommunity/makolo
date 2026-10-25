from django.urls import path

from .native_checkout_api import PersonalCommerceCheckoutAPIView

app_name = "commerce_api"

urlpatterns = [
    path("journeys/<uuid:journey_id>/checkout/", PersonalCommerceCheckoutAPIView.as_view(), name="journey-checkout"),
]

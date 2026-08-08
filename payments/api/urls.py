from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentConfigurationAPIView,
    PaymentEventViewSet,
    PaymentViewSet,
    SandboxWebhookAPIView,
)


router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("events", PaymentEventViewSet, basename="payment-event")

urlpatterns = [
    path("configuration/", PaymentConfigurationAPIView.as_view(), name="configuration"),
    path("webhooks/sandbox/", SandboxWebhookAPIView.as_view(), name="sandbox-webhook"),
    path("", include(router.urls)),
]

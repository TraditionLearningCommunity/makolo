from django.urls import path

from .views import (
    PromotionCodeListCreateAPIView,
    PromotionCodeToggleAPIView,
    PromotionDetailAPIView,
    PromotionListCreateAPIView,
    PromotionMetricsAPIView,
    PromotionRedemptionListAPIView,
    PromotionToggleAPIView,
)


urlpatterns = [
    path("promotions/", PromotionListCreateAPIView.as_view(), name="promotion-list"),
    path("promotions/<uuid:pk>/", PromotionDetailAPIView.as_view(), name="promotion-detail"),
    path("promotions/<uuid:pk>/toggle/", PromotionToggleAPIView.as_view(), name="promotion-toggle"),
    path("promotions/<uuid:pk>/metrics/", PromotionMetricsAPIView.as_view(), name="promotion-metrics"),
    path("codes/", PromotionCodeListCreateAPIView.as_view(), name="code-list"),
    path("codes/<uuid:pk>/toggle/", PromotionCodeToggleAPIView.as_view(), name="code-toggle"),
    path("redemptions/", PromotionRedemptionListAPIView.as_view(), name="redemption-list"),
]

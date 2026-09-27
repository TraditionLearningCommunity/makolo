from django.urls import path

from .views import (
    MyRecognitionAPIView,
    RecognitionRedemptionDecisionAPIView,
    RecognitionRewardRedeemAPIView,
    SpaceRecognitionAPIView,
    SpaceRecognitionRewardRedeemAPIView,
    SpaceRecognitionRedemptionDecisionAPIView,
)


app_name = "recognition_api"

urlpatterns = [
    path("spaces/<uuid:space_id>/", SpaceRecognitionAPIView.as_view(), name="space"),
    path("spaces/<uuid:space_id>/rewards/<uuid:reward_id>/redeem/", SpaceRecognitionRewardRedeemAPIView.as_view(), name="space-reward-redeem"),
    path("spaces/<uuid:space_id>/redemptions/<uuid:redemption_id>/<str:decision>/", SpaceRecognitionRedemptionDecisionAPIView.as_view(), name="space-redemption-decision"),
    path("me/", MyRecognitionAPIView.as_view(), name="me"),
    path(
        "rewards/<uuid:reward_id>/redeem/",
        RecognitionRewardRedeemAPIView.as_view(),
        name="reward-redeem",
    ),
    path(
        "redemptions/<uuid:redemption_id>/<str:decision>/",
        RecognitionRedemptionDecisionAPIView.as_view(),
        name="redemption-decision",
    ),
]

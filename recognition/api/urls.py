from django.urls import path

from .views import (
    MyRecognitionAPIView,
    RecognitionRedemptionDecisionAPIView,
    RecognitionRewardRedeemAPIView,
)


app_name = "recognition_api"

urlpatterns = [
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

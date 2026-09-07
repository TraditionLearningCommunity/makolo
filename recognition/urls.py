from django.urls import path

from .views import RecognitionDashboardView, RedeemRewardView, SpaceRecognitionDashboardView

app_name = "recognition"

urlpatterns = [
    path("", RecognitionDashboardView.as_view(), name="dashboard"),
    path("spaces/<uuid:space_id>/", SpaceRecognitionDashboardView.as_view(), name="space-dashboard"),
    path("rewards/<uuid:reward_id>/use/", RedeemRewardView.as_view(), name="reward-use"),
]

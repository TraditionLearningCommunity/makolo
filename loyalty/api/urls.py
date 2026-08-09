from django.urls import path

from .views import (
    AccountAdjustAPIView,
    MembershipActivateAPIView,
    MembershipCancelAPIView,
    MembershipJoinAPIView,
    MyLoyaltyAPIView,
    OrganizationProgramAPIView,
    PlanCreateAPIView,
    ProgramListCreateAPIView,
    RewardCreateAPIView,
    RewardRedeemAPIView,
    TierCreateAPIView,
)

urlpatterns = [
    path("me/", MyLoyaltyAPIView.as_view(), name="me"),
    path("organizations/<slug:slug>/", OrganizationProgramAPIView.as_view(), name="organization-program"),
    path("memberships/join/", MembershipJoinAPIView.as_view(), name="membership-join"),
    path("memberships/<uuid:pk>/cancel/", MembershipCancelAPIView.as_view(), name="membership-cancel"),
    path("memberships/<uuid:pk>/activate/", MembershipActivateAPIView.as_view(), name="membership-activate"),
    path("rewards/<uuid:pk>/redeem/", RewardRedeemAPIView.as_view(), name="reward-redeem"),
    path("programs/", ProgramListCreateAPIView.as_view(), name="programs"),
    path("tiers/", TierCreateAPIView.as_view(), name="tiers"),
    path("plans/", PlanCreateAPIView.as_view(), name="plans"),
    path("rewards/", RewardCreateAPIView.as_view(), name="rewards"),
    path("accounts/<uuid:pk>/adjust/", AccountAdjustAPIView.as_view(), name="account-adjust"),
]

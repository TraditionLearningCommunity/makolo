from django.urls import path

from .views import (
    AccountAdjustView,
    LoyaltyDashboardView,
    LoyaltyWorkspaceView,
    MembershipActivateView,
    MembershipCancelView,
    MembershipJoinView,
    OrganizationLoyaltyPortalView,
    PlanEditView,
    ProgramEditView,
    RewardEditView,
    RewardRedeemView,
    TierEditView,
)

app_name = "loyalty"

urlpatterns = [
    path("", LoyaltyDashboardView.as_view(), name="dashboard"),
    path("o/<slug:slug>/", OrganizationLoyaltyPortalView.as_view(), name="portal"),
    path("memberships/<uuid:pk>/join/", MembershipJoinView.as_view(), name="membership-join"),
    path("memberships/<uuid:pk>/cancel/", MembershipCancelView.as_view(), name="membership-cancel"),
    path("memberships/<uuid:pk>/activate/", MembershipActivateView.as_view(), name="membership-activate"),
    path("rewards/<uuid:pk>/redeem/", RewardRedeemView.as_view(), name="reward-redeem"),
    path("accounts/<uuid:pk>/adjust/", AccountAdjustView.as_view(), name="account-adjust"),
    path("manage/<slug:slug>/", LoyaltyWorkspaceView.as_view(), name="workspace"),
    path("manage/<slug:slug>/program/", ProgramEditView.as_view(), name="program-edit"),
    path("manage/<slug:slug>/tiers/new/", TierEditView.as_view(), name="tier-create"),
    path("manage/<slug:slug>/tiers/<uuid:pk>/", TierEditView.as_view(), name="tier-edit"),
    path("manage/<slug:slug>/plans/new/", PlanEditView.as_view(), name="plan-create"),
    path("manage/<slug:slug>/plans/<uuid:pk>/", PlanEditView.as_view(), name="plan-edit"),
    path("manage/<slug:slug>/rewards/new/", RewardEditView.as_view(), name="reward-create"),
    path("manage/<slug:slug>/rewards/<uuid:pk>/", RewardEditView.as_view(), name="reward-edit"),
]

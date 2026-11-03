from .space_native_api_views import (
    SpaceSubscriptionAPIView,
    SpaceSubscriptionAddonRemoveAPIView,
    SpaceSubscriptionHistoryAPIView,
    SpaceSubscriptionObligationsAPIView,
    SpaceSubscriptionPlanAPIView,
    SpaceSubscriptionTransitionAPIView,
)
from django.urls import path

from .native_api_views import (
    PersonalSubscriptionAddonRemoveAPIView,
    PersonalSubscriptionAPIView,
    PersonalSubscriptionHistoryAPIView,
    PersonalSubscriptionObligationsAPIView,
    PersonalSubscriptionPlanAPIView,
    PersonalSubscriptionTransitionAPIView,
)

app_name = "subscriptions_native"
urlpatterns = [
    path("me/", PersonalSubscriptionAPIView.as_view(), name="me"),
    path("me/obligations/", PersonalSubscriptionObligationsAPIView.as_view(), name="obligations"),
    path("me/transitions/", PersonalSubscriptionHistoryAPIView.as_view(), name="history"),
    path("me/plans/<uuid:plan_version_id>/", PersonalSubscriptionPlanAPIView.as_view(), name="plan"),
    path("me/addons/<uuid:item_id>/remove/", PersonalSubscriptionAddonRemoveAPIView.as_view(), name="addon-remove"),
    path("me/transitions/<uuid:transition_id>/<str:operation>/", PersonalSubscriptionTransitionAPIView.as_view(), name="transition"),
]

urlpatterns += [
    path("spaces/<slug:slug>/", SpaceSubscriptionAPIView.as_view(), name="space"),
    path("spaces/<slug:slug>/obligations/", SpaceSubscriptionObligationsAPIView.as_view(), name="space-obligations"),
    path("spaces/<slug:slug>/transitions/", SpaceSubscriptionHistoryAPIView.as_view(), name="space-history"),
    path("spaces/<slug:slug>/plans/<uuid:plan_version_id>/", SpaceSubscriptionPlanAPIView.as_view(), name="space-plan"),
    path("spaces/<slug:slug>/addons/<uuid:item_id>/remove/", SpaceSubscriptionAddonRemoveAPIView.as_view(), name="space-addon-remove"),
    path("spaces/<slug:slug>/transitions/<uuid:transition_id>/<str:operation>/", SpaceSubscriptionTransitionAPIView.as_view(), name="space-transition"),
]

from .coverage_native_api import (
    AllocationBeneficiaryAPIView, CoverageAllocationCreateAPIView,
    CoverageCollectionAPIView, CoverageStateAPIView, UsePersonalBaseAPIView,
)

urlpatterns += [
    path("me/coverages/", CoverageCollectionAPIView.as_view(), name="personal-coverages"),
    path("me/coverages/<uuid:coverage_id>/allocations/", CoverageAllocationCreateAPIView.as_view(), name="personal-coverage-allocate"),
    path("me/coverages/<uuid:coverage_id>/state/", CoverageStateAPIView.as_view(), name="personal-coverage-state"),
    path("me/allocations/<uuid:allocation_id>/<str:operation>/", AllocationBeneficiaryAPIView.as_view(), name="personal-benefit-decision"),
    path("me/base/personal/", UsePersonalBaseAPIView.as_view(), name="personal-base"),
    path("spaces/<slug:slug>/coverages/", CoverageCollectionAPIView.as_view(), name="space-coverages"),
    path("spaces/<slug:slug>/coverages/<uuid:coverage_id>/allocations/", CoverageAllocationCreateAPIView.as_view(), name="space-coverage-allocate"),
    path("spaces/<slug:slug>/coverages/<uuid:coverage_id>/state/", CoverageStateAPIView.as_view(), name="space-coverage-state"),
    path("spaces/<slug:slug>/allocations/<uuid:allocation_id>/<str:operation>/", AllocationBeneficiaryAPIView.as_view(), name="space-benefit-decision"),
    path("spaces/<slug:slug>/base/personal/", UsePersonalBaseAPIView.as_view(), name="space-own-base"),
]

from .coverage_native_api_views import (
    PersonalCoverageAPIView,
    SpaceCoverageAPIView,
    CoverageManageAPIView,
    CoverageAllocationAPIView,
    CoverageStatusAPIView,
    PersonalCoverageDecisionAPIView,
    SpaceCoverageDecisionAPIView,
)

urlpatterns += [
    path("me/coverages/", PersonalCoverageAPIView.as_view(), name="me-coverages"),
    path("me/coverages/allocations/<uuid:allocation_id>/", PersonalCoverageDecisionAPIView.as_view(), name="me-coverage-decision"),
    path("spaces/<slug:slug>/coverages/", SpaceCoverageAPIView.as_view(), name="space-coverages"),
    path("spaces/<slug:slug>/coverages/allocations/<uuid:allocation_id>/", SpaceCoverageDecisionAPIView.as_view(), name="space-coverage-decision"),
    path("coverages/<uuid:coverage_id>/", CoverageManageAPIView.as_view(), name="funded-coverage"),
    path("coverages/<uuid:coverage_id>/allocations/", CoverageAllocationAPIView.as_view(), name="funded-coverage-allocations"),
    path("coverages/<uuid:coverage_id>/status/", CoverageStatusAPIView.as_view(), name="funded-coverage-status"),
]

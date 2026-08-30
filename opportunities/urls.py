from django.urls import path

from .staff_views import (
    OpportunityStaffCreateView,
    OpportunityStaffDashboardView,
    OpportunityStaffDetailView,
    OpportunityStaffLifecycleView,
    OpportunityStaffMergeView,
    OpportunityStaffPublishRevisionView,
    OpportunityStaffRevisionCreateView,
    OpportunityStaffSourceCheckView,
    OpportunityStaffSourceCreateView,
    OpportunityStaffSubmissionReviewView,
)
from .views import (
    OpportunityDetailView,
    OpportunityListView,
    OpportunitySaveToggleView,
    OpportunitySavedListView,
    OpportunitySubmissionCreateView,
    OpportunitySubmissionDetailView,
)

app_name = "opportunities"

urlpatterns = [
    path("", OpportunityListView.as_view(), name="list"),
    path("saved/", OpportunitySavedListView.as_view(), name="saved"),
    path("submit/", OpportunitySubmissionCreateView.as_view(), name="submit"),
    path("staff/", OpportunityStaffDashboardView.as_view(), name="staff-dashboard"),
    path("staff/new/", OpportunityStaffCreateView.as_view(), name="staff-create"),
    path("staff/submissions/<uuid:pk>/", OpportunityStaffSubmissionReviewView.as_view(), name="staff-submission-review"),
    path("staff/<uuid:pk>/", OpportunityStaffDetailView.as_view(), name="staff-detail"),
    path("staff/<uuid:pk>/revisions/new/", OpportunityStaffRevisionCreateView.as_view(), name="staff-revision-create"),
    path("staff/<uuid:pk>/revisions/<uuid:revision_pk>/publish/", OpportunityStaffPublishRevisionView.as_view(), name="staff-revision-publish"),
    path("staff/<uuid:pk>/sources/new/", OpportunityStaffSourceCreateView.as_view(), name="staff-source-create"),
    path("staff/<uuid:pk>/sources/<uuid:source_pk>/check/", OpportunityStaffSourceCheckView.as_view(), name="staff-source-check"),
    path("staff/<uuid:pk>/lifecycle/", OpportunityStaffLifecycleView.as_view(), name="staff-lifecycle"),
    path("staff/<uuid:pk>/merge/", OpportunityStaffMergeView.as_view(), name="staff-merge"),
    path("submissions/<uuid:pk>/", OpportunitySubmissionDetailView.as_view(), name="submission-detail"),
    path("<uuid:pk>/", OpportunityDetailView.as_view(), name="detail"),
    path("<uuid:pk>/save/", OpportunitySaveToggleView.as_view(), name="save-toggle"),
]
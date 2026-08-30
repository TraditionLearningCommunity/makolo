from django.urls import path

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
    path("submissions/<uuid:pk>/", OpportunitySubmissionDetailView.as_view(), name="submission-detail"),
    path("<uuid:pk>/", OpportunityDetailView.as_view(), name="detail"),
    path("<uuid:pk>/save/", OpportunitySaveToggleView.as_view(), name="save-toggle"),
]

from django.urls import path

from .api_views import (
    ActionStreamAPIView,
    ContributionReportAPIView,
    GroupContributionAPIView,
    GroupShareAPIView,
    RecommendationsAPIView,
    ReplyAPIView,
)

urlpatterns = [
    path("stream/", ActionStreamAPIView.as_view(), name="social-stream-api"),
    path("recommendations/", RecommendationsAPIView.as_view(), name="social-recommendations-api"),
    path("groups/<uuid:group_id>/contributions/", GroupContributionAPIView.as_view(), name="social-group-contribution-api"),
    path("groups/<uuid:group_id>/share-activity/", GroupShareAPIView.as_view(), name="social-group-share-api"),
    path("contributions/<uuid:contribution_id>/reply/", ReplyAPIView.as_view(), name="social-reply-api"),
    path("contributions/<uuid:contribution_id>/report/", ContributionReportAPIView.as_view(), name="social-report-api"),
]

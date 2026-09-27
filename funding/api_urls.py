from django.urls import path

from .api_views import (
    FundingContributionAPIView,
    FundingDetailAPIView,
    FundingListCreateAPIView,
)


app_name = "funding_api"

urlpatterns = [
    path("", FundingListCreateAPIView.as_view(), name="list-create"),
    path("<uuid:pk>/", FundingDetailAPIView.as_view(), name="detail"),
    path("<uuid:pk>/contributions/", FundingContributionAPIView.as_view(), name="contribute"),
]

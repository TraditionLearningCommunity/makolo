from django.urls import path

from .views import FollowDetailAPIView, FollowListCreateAPIView


app_name = "organizations_api"

urlpatterns = [
    path("follows/", FollowListCreateAPIView.as_view(), name="follows"),
    path("follows/<uuid:pk>/", FollowDetailAPIView.as_view(), name="follow-detail"),
]

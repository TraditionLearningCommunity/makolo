from django.urls import path

from .api_views import ActivityDetailAPIView

app_name = "activities_api"

urlpatterns = [
    path("<uuid:pk>/", ActivityDetailAPIView.as_view(), name="detail"),
]

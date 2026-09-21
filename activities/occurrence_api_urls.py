from django.urls import path

from .api_views import OccurrenceDetailAPIView

app_name = "occurrences_api"

urlpatterns = [
    path("<uuid:pk>/", OccurrenceDetailAPIView.as_view(), name="detail"),
]

from django.urls import path

from .api_views import ServiceStartAPIView


app_name = "services-api"

urlpatterns = [
    path("<uuid:pk>/start/", ServiceStartAPIView.as_view(), name="start"),
]

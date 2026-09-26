from django.urls import path

from .platform_views import PlatformCapabilitiesAPIView


app_name = "platform_api"

urlpatterns = [
    path("capabilities/", PlatformCapabilitiesAPIView.as_view(), name="capabilities"),
]

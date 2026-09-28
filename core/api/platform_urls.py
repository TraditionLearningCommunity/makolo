from django.urls import path

from interoperability.api_views import PlatformInteroperabilityAPIView

from .platform_views import PlatformCapabilitiesAPIView


app_name = "platform_api"

urlpatterns = [
    path("capabilities/", PlatformCapabilitiesAPIView.as_view(), name="capabilities"),
    path("interoperability/", PlatformInteroperabilityAPIView.as_view(), name="interoperability"),
]

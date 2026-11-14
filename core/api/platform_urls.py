from django.urls import path

from interoperability.api_views import PlatformInteroperabilityAPIView
from intelligence.connection_api import (
    PlatformIntelligenceConnectionsAPIView, PlatformIntelligenceConnectionAPIView,
)


from .platform_views import PlatformCapabilitiesAPIView


app_name = "platform_api"

urlpatterns = [
    path("capabilities/", PlatformCapabilitiesAPIView.as_view(), name="capabilities"),
    path("interoperability/", PlatformInteroperabilityAPIView.as_view(), name="interoperability"),
    path("intelligence/connections/", PlatformIntelligenceConnectionsAPIView.as_view(), name="intelligence-connections"),
    path("intelligence/connections/<uuid:connection_id>/", PlatformIntelligenceConnectionAPIView.as_view(), name="intelligence-connection"),
]

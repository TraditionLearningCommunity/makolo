from django.urls import path

from .platform_web_views import (
    PlatformAuditView, PlatformHomeView, PlatformInteroperabilityView,
    PlatformInvestigateView, PlatformOperationsView, PlatformRecognitionSimulationView,
    PlatformRecognitionView, PlatformSystemView,
)

app_name = "platform_web"

urlpatterns = [
    path("", PlatformHomeView.as_view(), name="home"),
    path("investigate/", PlatformInvestigateView.as_view(), name="investigate"),
    path("operations/", PlatformOperationsView.as_view(), name="operations"),
    path("system/", PlatformSystemView.as_view(), name="system"),
    path("audit/", PlatformAuditView.as_view(), name="audit"),
    path("interoperability/", PlatformInteroperabilityView.as_view(), name="interoperability"),
    path("recognition/", PlatformRecognitionView.as_view(), name="recognition"),
    path("recognition/<uuid:pk>/simulation/", PlatformRecognitionSimulationView.as_view(), name="recognition-simulation"),
]

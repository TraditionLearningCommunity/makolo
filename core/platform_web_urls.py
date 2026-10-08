from django.urls import path

from .platform_web_views import (
    PlatformAuditView, PlatformHomeView, PlatformInteroperabilityView,
    PlatformInvestigateView, PlatformOperationsView, PlatformRecognitionSimulationView,
    PlatformRecognitionView, PlatformRecognitionActionView, PlatformSystemView, PlatformSpaceDecisionView, PlatformEventDecisionView,
)

app_name = "platform_web"

urlpatterns = [
    path("", PlatformHomeView.as_view(), name="home"),
    path("investigate/", PlatformInvestigateView.as_view(), name="investigate"),
    path("operations/", PlatformOperationsView.as_view(), name="operations"),
    path("operations/spaces/<uuid:pk>/decide/", PlatformSpaceDecisionView.as_view(), name="space-decision"),
    path("operations/events/<uuid:pk>/decide/", PlatformEventDecisionView.as_view(), name="event-decision"),
    path("system/", PlatformSystemView.as_view(), name="system"),
    path("audit/", PlatformAuditView.as_view(), name="audit"),
    path("interoperability/", PlatformInteroperabilityView.as_view(), name="interoperability"),
    path("recognition/", PlatformRecognitionView.as_view(), name="recognition"),
    path("recognition/<uuid:pk>/simulation/", PlatformRecognitionSimulationView.as_view(), name="recognition-simulation"),
    path("recognition/<uuid:pk>/<str:action>/", PlatformRecognitionActionView.as_view(), name="recognition-action"),
]

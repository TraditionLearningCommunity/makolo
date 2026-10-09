from django.urls import path
from .platform_trust_views import PlatformTrustCaseView
from .platform_curation_views import PlatformCurationDecisionView, PlatformCurationDetailView

from .platform_web_views import (
    PlatformAuditView, PlatformHomeView, PlatformInteroperabilityView,
    PlatformInvestigateView, PlatformOperationsView, PlatformTrustView, PlatformCurationView, PlatformOpportunityMergeView, PlatformSubscriptionsView, PlatformRecognitionSimulationView,
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
    path("trust/", PlatformTrustView.as_view(), name="trust"),
    path("trust/<str:case_type>/<uuid:pk>/", PlatformTrustCaseView.as_view(), name="trust-case"),
    path("curation/", PlatformCurationView.as_view(), name="curation"),
    path("curation/<uuid:pk>/", PlatformCurationDetailView.as_view(), name="curation-detail"),
    path("curation/<uuid:pk>/decide/", PlatformCurationDecisionView.as_view(), name="curation-decision"),
    path("curation/<uuid:pk>/merge/", PlatformOpportunityMergeView.as_view(), name="opportunity-merge"),
    path("subscriptions/", PlatformSubscriptionsView.as_view(), name="subscriptions"),
    path("interoperability/", PlatformInteroperabilityView.as_view(), name="interoperability"),
    path("recognition/", PlatformRecognitionView.as_view(), name="recognition"),
    path("recognition/<uuid:pk>/simulation/", PlatformRecognitionSimulationView.as_view(), name="recognition-simulation"),
    path("recognition/<uuid:pk>/<str:action>/", PlatformRecognitionActionView.as_view(), name="recognition-action"),
]

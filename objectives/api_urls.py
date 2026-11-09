from django.urls import path

from .dossier_api import DossierActionsAPIView

from .project_api import (
    ProjectDossiersAPIView, ProjectDossierActionAPIView,
    ProjectLifecycleAPIView, ProjectAuthorityAPIView,
)

from .api_views import (
    DossierCollectionAPIView,
    DossierDetailAPIView,
    OrganizerCollectionAPIView,
    ProjectCollectionAPIView,
    ProjectDetailAPIView,
)

app_name = "objectives_api"

urlpatterns = [
    path("organizer/", OrganizerCollectionAPIView.as_view(), name="organizer"),
    path("dossiers/", DossierCollectionAPIView.as_view(), name="dossier-list"),
    path("projects/", ProjectCollectionAPIView.as_view(), name="project-list"),
    path("dossiers/<uuid:pk>/", DossierDetailAPIView.as_view(), name="dossier-detail"),
    path("dossiers/<uuid:pk>/actions/", DossierActionsAPIView.as_view(), name="dossier-actions"),
    path("projects/<uuid:pk>/", ProjectDetailAPIView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/dossiers/", ProjectDossiersAPIView.as_view(), name="project-dossiers"),
    path("projects/<uuid:pk>/dossiers/<uuid:dossier_id>/", ProjectDossierActionAPIView.as_view(), name="project-dossier-action"),
    path("projects/<uuid:pk>/authority/", ProjectAuthorityAPIView.as_view(), name="project-authority"),
    path("projects/<uuid:pk>/lifecycle/", ProjectLifecycleAPIView.as_view(), name="project-lifecycle"),
]

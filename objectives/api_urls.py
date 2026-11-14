from django.urls import path

from .dossier_api import DossierActionsAPIView

from .project_api import (
    ProjectDossiersAPIView, ProjectDossierActionAPIView,
    ProjectLifecycleAPIView, ProjectAuthorityAPIView,
    ProjectPeopleSearchAPIView, ProjectInvitationCreateAPIView,
    ProjectInvitationInboxAPIView, ProjectInvitationRespondAPIView,
    ProjectInvitationCancelAPIView,
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
    path("projects/invitations/", ProjectInvitationInboxAPIView.as_view(), name="project-invitations"),
    path("projects/invitations/<uuid:pk>/respond/", ProjectInvitationRespondAPIView.as_view(), name="project-invitation-respond"),
    path("projects/invitations/<uuid:pk>/cancel/", ProjectInvitationCancelAPIView.as_view(), name="project-invitation-cancel"),

    path("dossiers/<uuid:pk>/", DossierDetailAPIView.as_view(), name="dossier-detail"),
    path("dossiers/<uuid:pk>/actions/", DossierActionsAPIView.as_view(), name="dossier-actions"),
    path("projects/<uuid:pk>/", ProjectDetailAPIView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/dossiers/", ProjectDossiersAPIView.as_view(), name="project-dossiers"),
    path("projects/<uuid:pk>/dossiers/<uuid:dossier_id>/", ProjectDossierActionAPIView.as_view(), name="project-dossier-action"),
    path("projects/<uuid:pk>/authority/", ProjectAuthorityAPIView.as_view(), name="project-authority"),
    path("projects/<uuid:pk>/people/search/", ProjectPeopleSearchAPIView.as_view(), name="project-people-search"),
    path("projects/<uuid:pk>/invitations/", ProjectInvitationCreateAPIView.as_view(), name="project-invite"),

    path("projects/<uuid:pk>/lifecycle/", ProjectLifecycleAPIView.as_view(), name="project-lifecycle"),
]

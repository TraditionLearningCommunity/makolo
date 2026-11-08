from django.urls import path

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
    path("projects/<uuid:pk>/", ProjectDetailAPIView.as_view(), name="project-detail"),
]

from django.urls import path

from .api_views import DossierDetailAPIView, ProjectDetailAPIView

app_name = "objectives_api"

urlpatterns = [
    path("dossiers/<uuid:pk>/", DossierDetailAPIView.as_view(), name="dossier-detail"),
    path("projects/<uuid:pk>/", ProjectDetailAPIView.as_view(), name="project-detail"),
]

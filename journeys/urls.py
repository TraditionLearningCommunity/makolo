from django.urls import path

from . import views


app_name = "journeys"

urlpatterns = [
    path("artifacts/<uuid:artifact_id>/download/", views.download_artifact, name="artifact-download"),
]

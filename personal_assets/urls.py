from django.urls import path

from . import views


app_name = "personal_assets"

urlpatterns = [
    path("", views.library_list, name="list"),
    path("add/", views.library_add, name="add"),
    path("<uuid:asset_id>/", views.library_detail, name="detail"),
    path("<uuid:asset_id>/version/", views.library_add_version, name="add-version"),
    path("<uuid:asset_id>/archive/", views.library_archive, name="archive"),
    path("versions/<uuid:version_id>/download/", views.library_download, name="download"),
    path("journeys/<uuid:journey_id>/use/", views.library_use_in_journey, name="use-in-journey"),
    path("journey-artifacts/<uuid:artifact_id>/save/", views.journey_artifact_save_to_library, name="save-artifact"),
]

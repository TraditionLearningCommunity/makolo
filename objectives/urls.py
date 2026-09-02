from django.urls import path

from . import views


app_name = "objectives"

urlpatterns = [
    path("", views.dossier_list, name="dossier-list"),
    path("new/", views.dossier_create, name="dossier-create"),
    path("<uuid:dossier_id>/", views.dossier_detail, name="dossier-detail"),
    path("<uuid:dossier_id>/journeys/link/", views.dossier_link_journey, name="dossier-link-journey"),
    path("<uuid:dossier_id>/journeys/<uuid:journey_id>/unlink/", views.dossier_unlink_journey, name="dossier-unlink-journey"),
    path("<uuid:dossier_id>/dependencies/add/", views.dossier_add_dependency, name="dossier-add-dependency"),
    path(
        "<uuid:dossier_id>/dependencies/<uuid:dependency_id>/remove/",
        views.dossier_remove_dependency,
        name="dossier-remove-dependency",
    ),
    path(
        "<uuid:dossier_id>/dependencies/<uuid:dependency_id>/waive/",
        views.dossier_waive_dependency,
        name="dossier-waive-dependency",
    ),
    path("<uuid:dossier_id>/lifecycle/", views.dossier_lifecycle, name="dossier-lifecycle"),
]

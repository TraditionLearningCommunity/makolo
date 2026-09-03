from django.urls import path

from . import views


app_name = "objectives"

urlpatterns = [
    path("", views.dossier_list, name="dossier-list"),
    path("new/", views.dossier_create, name="dossier-create"),
    path("projects/", views.project_list, name="project-list"),
    path("projects/new/", views.project_create, name="project-create"),
    path("projects/<uuid:project_id>/", views.project_detail, name="project-detail"),
    path("projects/<uuid:project_id>/dossiers/link/", views.project_link_dossier, name="project-link-dossier"),
    path("projects/<uuid:project_id>/dossiers/<uuid:dossier_id>/unlink/", views.project_unlink_dossier, name="project-unlink-dossier"),
    path("projects/<uuid:project_id>/lifecycle/", views.project_lifecycle, name="project-lifecycle"),
    path("<uuid:dossier_id>/", views.dossier_detail, name="dossier-detail"),
    path("<uuid:dossier_id>/project/", views.dossier_project, name="dossier-project"),
    path("<uuid:dossier_id>/collaboration/assign/", views.dossier_assign, name="dossier-assign"),
    path("<uuid:dossier_id>/collaboration/<uuid:assignment_id>/remove/", views.dossier_unassign, name="dossier-unassign"),
    path("<uuid:dossier_id>/authority/grant/", views.dossier_grant_authority, name="dossier-grant-authority"),
    path("<uuid:dossier_id>/authority/<uuid:mandate_id>/revoke/", views.dossier_revoke_authority, name="dossier-revoke-authority"),
    path("<uuid:dossier_id>/journeys/link/", views.dossier_link_journey, name="dossier-link-journey"),
    path("<uuid:dossier_id>/journeys/<uuid:journey_id>/unlink/", views.dossier_unlink_journey, name="dossier-unlink-journey"),
    path("<uuid:dossier_id>/dependencies/add/", views.dossier_add_dependency, name="dossier-add-dependency"),
    path("<uuid:dossier_id>/dependencies/<uuid:dependency_id>/remove/", views.dossier_remove_dependency, name="dossier-remove-dependency"),
    path("<uuid:dossier_id>/dependencies/<uuid:dependency_id>/waive/", views.dossier_waive_dependency, name="dossier-waive-dependency"),
    path("<uuid:dossier_id>/lifecycle/", views.dossier_lifecycle, name="dossier-lifecycle"),
]

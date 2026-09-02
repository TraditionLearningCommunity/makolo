from django.urls import path

from . import views


app_name = "objectives"

urlpatterns = [
    path("", views.dossier_list, name="dossier-list"),
    path("new/", views.dossier_create, name="dossier-create"),
    path("<uuid:dossier_id>/", views.dossier_detail, name="dossier-detail"),
    path("<uuid:dossier_id>/journeys/link/", views.dossier_link_journey, name="dossier-link-journey"),
    path("<uuid:dossier_id>/journeys/<uuid:journey_id>/unlink/", views.dossier_unlink_journey, name="dossier-unlink-journey"),
    path("<uuid:dossier_id>/lifecycle/", views.dossier_lifecycle, name="dossier-lifecycle"),
]

from django.urls import path

from .views import ManageResourcesView, ResourceDownloadView, ResourceTextReadView


app_name = "preparation"

urlpatterns = [
    path("resources/<uuid:resource_id>/download/", ResourceDownloadView.as_view(), name="resource-download"),
    path("resources/<uuid:resource_id>/text/", ResourceTextReadView.as_view(), name="resource-text"),
    path("manage/activity/<uuid:activity_id>/", ManageResourcesView.as_view(), name="manage"),
]

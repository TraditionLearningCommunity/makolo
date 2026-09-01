from django.urls import path

from .views import ManageResourcesView, ResourceDownloadView


app_name = "preparation"

urlpatterns = [
    path("resources/<uuid:resource_id>/download/", ResourceDownloadView.as_view(), name="resource-download"),
    path("manage/activity/<uuid:activity_id>/", ManageResourcesView.as_view(), name="manage"),
]

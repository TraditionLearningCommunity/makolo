from django.urls import path

from .views import ActivityPresentationPreviewView, ActivityPresentationStudioView, ParticipantAccessPresentationView, PublicActivityPresentationView

app_name = "presentations"

urlpatterns = [
    path("activity/<uuid:activity_id>/studio/", ActivityPresentationStudioView.as_view(), name="studio"),
    path("activity/<uuid:activity_id>/preview/", ActivityPresentationPreviewView.as_view(), name="preview"),
    path("activity/<uuid:activity_id>/", PublicActivityPresentationView.as_view(), name="public-activity"),
    path("access/<uuid:access_id>/", ParticipantAccessPresentationView.as_view(), name="participant-access"),
]

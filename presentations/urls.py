from django.urls import path

from .library_views import ActivateTemplateVersionView, DuplicateTemplateView, ModerateTemplateView, PresentationLibraryView, SetSpaceDefaultView, SpacePresentationLibraryView, SubmitTemplateView, TemplateVersionPreviewView
from .views import ActivityArtifactPresentationView, ActivityPresentationPreviewView, ActivityPresentationStudioView, ParticipantAccessPresentationView, ParticipantJourneyPresentationView, PublicActivityPresentationView

app_name = "presentations"

urlpatterns = [
    path("activity/<uuid:activity_id>/studio/", ActivityPresentationStudioView.as_view(), name="studio"),
    path("activity/<uuid:activity_id>/preview/", ActivityPresentationPreviewView.as_view(), name="preview"),
    path("activity/<uuid:activity_id>/artifact/<str:purpose>/", ActivityArtifactPresentationView.as_view(), name="activity-artifact"),
    path("activity/<uuid:activity_id>/", PublicActivityPresentationView.as_view(), name="public-activity"),
    path("journey/<uuid:journey_id>/invitation/", ParticipantJourneyPresentationView.as_view(), name="participant-invitation"),
    path("access/<uuid:access_id>/", ParticipantAccessPresentationView.as_view(), name="participant-access"),
    path("library/", PresentationLibraryView.as_view(), name="library"),
    path("library/space/<slug:slug>/", SpacePresentationLibraryView.as_view(), name="space-library"),
    path("library/space/<slug:slug>/default/", SetSpaceDefaultView.as_view(), name="space-default"),
    path("library/version/<int:version_id>/preview/", TemplateVersionPreviewView.as_view(), name="template-preview"),
    path("library/version/<int:version_id>/activate/", ActivateTemplateVersionView.as_view(), name="activate-template"),
    path("library/version/<int:version_id>/duplicate/", DuplicateTemplateView.as_view(), name="duplicate-template"),
    path("library/version/<int:version_id>/submit/", SubmitTemplateView.as_view(), name="submit-template"),
    path("library/version/<int:version_id>/<str:action>/", ModerateTemplateView.as_view(), name="moderate-template"),
]

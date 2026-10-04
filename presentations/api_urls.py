from django.urls import path

from .api_views import (
    ActivityPresentationAPIView,
    ActivityTemplateAPIView,
    ActivityThemeAPIView,
    PersonalAccessPresentationAPIView,
    PersonalAccessTemplateAPIView,
    PersonalAccessThemeAPIView,
)

app_name = "presentations-api"

urlpatterns = [
    path(
        "accesses/<uuid:pk>/",
        PersonalAccessPresentationAPIView.as_view(),
        name="access-artifact",
    ),
    path(
        "accesses/<uuid:pk>/templates/<int:version_id>/",
        PersonalAccessTemplateAPIView.as_view(),
        name="access-template",
    ),
    path(
        "accesses/<uuid:pk>/themes/<int:version_id>/",
        PersonalAccessThemeAPIView.as_view(),
        name="access-theme",
    ),
    path(
        "activities/<uuid:pk>/<str:purpose>/",
        ActivityPresentationAPIView.as_view(),
        name="activity-artifact",
    ),
    path(
        "activities/<uuid:pk>/<str:purpose>/templates/<int:version_id>/",
        ActivityTemplateAPIView.as_view(),
        name="activity-template",
    ),
    path(
        "activities/<uuid:pk>/<str:purpose>/themes/<int:version_id>/",
        ActivityThemeAPIView.as_view(),
        name="activity-theme",
    ),
]

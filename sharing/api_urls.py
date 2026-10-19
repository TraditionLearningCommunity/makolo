from django.urls import path

from .api_views import (
    PublicShareResolveAPIView,
    SharePossibilityAPIView,
    ShareRecipientSearchAPIView,
)

app_name = "sharing_api"

urlpatterns = [
    path("recipients/", ShareRecipientSearchAPIView.as_view(), name="recipients"),
    path(
        "possibilities/<str:family>/<uuid:item_id>/",
        SharePossibilityAPIView.as_view(),
        name="possibility",
    ),
    path(
        "resolve/<str:token>/",
        PublicShareResolveAPIView.as_view(),
        name="resolve",
    ),
]

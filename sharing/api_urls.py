from django.urls import path

from .passport_reader_api import (
    PassportSharedReaderAPIView, PassportVerificationReaderAPIView,
)

from .api_views import (
    PublicShareResolveAPIView,
    ShareDeliveryResolveAPIView,
    SharePossibilityAPIView,
    ShareRecipientSearchAPIView,
)

app_name = "sharing_api"

urlpatterns = [
    path("passport/verify/<str:token>/", PassportVerificationReaderAPIView.as_view(), name="passport-verify-reader"),
    path("passport/shared/<str:token>/", PassportSharedReaderAPIView.as_view(), name="passport-shared-reader"),
    path("recipients/", ShareRecipientSearchAPIView.as_view(), name="recipients"),
    path("deliveries/<uuid:delivery_id>/", ShareDeliveryResolveAPIView.as_view(), name="delivery"),
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

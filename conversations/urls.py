from django.urls import path

from .media_views import serve_attachment
from .views import (
    ConversationDetailView,
    ConversationInvitationRespondView,
    ConversationListView,
    PointAcknowledgeView,
    PointExchangeView,
    PointRespondView,
)


app_name = "conversations"

urlpatterns = [
    path("", ConversationListView.as_view(), name="list"),
    path("<uuid:pk>/", ConversationDetailView.as_view(), name="detail"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondView.as_view(), name="invitation-respond"),
    path("points/<uuid:point_pk>/respond/", PointRespondView.as_view(), name="point-respond"),
    path("points/<uuid:point_pk>/acknowledge/", PointAcknowledgeView.as_view(), name="point-acknowledge"),
    path("points/<uuid:point_pk>/exchange/", PointExchangeView.as_view(), name="point-exchange"),
    path("attachments/<uuid:attachment_pk>/", serve_attachment, name="attachment"),
]

from django.urls import path

from .api_views import (
    ConversationDetailAPIView,
    ConversationInvitationListAPIView,
    ConversationInvitationRespondAPIView,
    ConversationListAPIView,
    ConversationPointAcknowledgeAPIView,
    ConversationPointResponseAPIView,
)


app_name = "conversations-api"

urlpatterns = [
    path("", ConversationListAPIView.as_view(), name="list"),
    path("<uuid:pk>/", ConversationDetailAPIView.as_view(), name="detail"),
    path("points/<uuid:point_pk>/respond/", ConversationPointResponseAPIView.as_view(), name="point-respond"),
    path("points/<uuid:point_pk>/acknowledge/", ConversationPointAcknowledgeAPIView.as_view(), name="point-acknowledge"),
    path("invitations/", ConversationInvitationListAPIView.as_view(), name="invitation-list"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondAPIView.as_view(), name="invitation-respond"),
]

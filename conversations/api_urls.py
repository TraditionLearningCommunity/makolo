from django.urls import path

from .api_views import (
    ConversationAttentionPresenceAPIView,
    ConversationDetailAPIView,
    ConversationInvitationListAPIView,
    ConversationInvitationRespondAPIView,
    ConversationListAPIView,
    ConversationPersonalStateAPIView,
    ConversationPointAcknowledgeAPIView,
    ConversationPointResponseAPIView,
)


app_name = "conversations-api"

urlpatterns = [
    path("", ConversationListAPIView.as_view(), name="list"),
    path("attention-presence/", ConversationAttentionPresenceAPIView.as_view(), name="attention-presence"),
    path("<uuid:pk>/", ConversationDetailAPIView.as_view(), name="detail"),
    path("<uuid:pk>/personal-state/", ConversationPersonalStateAPIView.as_view(), name="personal-state"),
    path("points/<uuid:point_pk>/respond/", ConversationPointResponseAPIView.as_view(), name="point-respond"),
    path("points/<uuid:point_pk>/acknowledge/", ConversationPointAcknowledgeAPIView.as_view(), name="point-acknowledge"),
    path("invitations/", ConversationInvitationListAPIView.as_view(), name="invitation-list"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondAPIView.as_view(), name="invitation-respond"),
]

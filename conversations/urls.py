from django.urls import path

from .media_views import serve_attachment
from .views import (
    ConversationDetailView,
    ConversationContextOpenView,
    ConversationContextEnsureView,
    ConversationComposeView,
    ConversationMediaWebView,
    ConversationExchangeDepthView,
    ConversationInvitationRespondView,
    ConversationListView,
    PointAcknowledgeView,
    PointExchangeView,
    PointRespondView,
)


app_name = "conversations"

urlpatterns = [
    path("", ConversationListView.as_view(), name="list"),
    path("by-context/<str:kind>/<str:context_pk>/", ConversationContextOpenView.as_view(), name="by-context"),
    path("<uuid:pk>/", ConversationDetailView.as_view(), name="detail"),
    path("<uuid:pk>/compose/", ConversationComposeView.as_view(), name="compose"),
    path("<uuid:pk>/media/", ConversationMediaWebView.as_view(), name="media"),
    path("points/<uuid:point_pk>/", ConversationExchangeDepthView.as_view(), name="exchange-detail"),
    path("by-context/<str:kind>/<str:context_pk>/ensure/", ConversationContextEnsureView.as_view(), name="context-ensure"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondView.as_view(), name="invitation-respond"),
    path("points/<uuid:point_pk>/respond/", PointRespondView.as_view(), name="point-respond"),
    path("points/<uuid:point_pk>/acknowledge/", PointAcknowledgeView.as_view(), name="point-acknowledge"),
    path("points/<uuid:point_pk>/exchange/", PointExchangeView.as_view(), name="point-exchange"),
    path("attachments/<uuid:attachment_pk>/", serve_attachment, name="attachment"),
]

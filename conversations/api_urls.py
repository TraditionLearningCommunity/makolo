from django.urls import path

from .api_views import (
    ConversationAttentionPresenceAPIView,
    ConversationDetailAPIView,
    ConversationPointsDepthAPIView,
    ConversationComposeAPIView,
    ConversationFormOptionsAPIView,
    ConversationPointMediaResponseAPIView,
    ConversationFormComposeAPIView,
    ConversationMediaUploadAPIView,
    ConversationSemanticMediaAPIView,
    ConversationAttachmentDownloadAPIView,
    ConversationExchangeEntriesAPIView,
    ConversationContextEnsureAPIView,
    ConversationContextLookupAPIView,
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
    path("by-context/<str:kind>/<str:context_pk>/", ConversationContextLookupAPIView.as_view(), name="by-context"),
    path("by-context/<str:kind>/<str:context_pk>/ensure/", ConversationContextEnsureAPIView.as_view(), name="context-ensure"),
    path("<uuid:pk>/", ConversationDetailAPIView.as_view(), name="detail"),
    path("<uuid:pk>/points/", ConversationPointsDepthAPIView.as_view(), name="point-depth"),
    path("<uuid:pk>/compose/", ConversationComposeAPIView.as_view(), name="compose"),
    path("<uuid:pk>/forms/options/", ConversationFormOptionsAPIView.as_view(), name="form-options"),
    path("<uuid:pk>/forms/", ConversationFormComposeAPIView.as_view(), name="form-compose"),
    path("<uuid:pk>/media/", ConversationMediaUploadAPIView.as_view(), name="media-upload"),
    path("<uuid:pk>/semantic-media/", ConversationSemanticMediaAPIView.as_view(), name="semantic-media"),
    path("attachments/<uuid:attachment_pk>/download/", ConversationAttachmentDownloadAPIView.as_view(), name="attachment-download"),
    path("points/<uuid:point_pk>/entries/", ConversationExchangeEntriesAPIView.as_view(), name="exchange-entries"),
    path("points/<uuid:point_pk>/entries/", ConversationExchangeEntriesAPIView.as_view(), name="exchange-entry"),
    # GET and POST share the same guarded owner endpoint.

    path("<uuid:pk>/personal-state/", ConversationPersonalStateAPIView.as_view(), name="personal-state"),
    path("points/<uuid:point_pk>/respond/", ConversationPointResponseAPIView.as_view(), name="point-respond"),
    path("points/<uuid:point_pk>/reply-media/", ConversationPointMediaResponseAPIView.as_view(), name="point-reply-media"),
    path("points/<uuid:point_pk>/acknowledge/", ConversationPointAcknowledgeAPIView.as_view(), name="point-acknowledge"),
    path("invitations/", ConversationInvitationListAPIView.as_view(), name="invitation-list"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondAPIView.as_view(), name="invitation-respond"),
]

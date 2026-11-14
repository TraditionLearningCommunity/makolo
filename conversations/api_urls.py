from django.urls import path
from .realtime_api import ConversationRealtimeTicketAPIView
from .entry_api import (ConversationEntrySyncAPIView, ConversationEntryDetailAPIView,
                        ConversationEntryReactionAPIView, ConversationEntrySearchAPIView,
                        ConversationEntryReceiptsAPIView, ConversationEntryMentionCandidatesAPIView,
                        ConversationEntryReferenceAPIView, ConversationEntryReferenceOptionsAPIView, ConversationEntryReferenceFileAPIView)

from .api_views import (
    ConversationAttentionPresenceAPIView,
    ConversationAttentionAPIView,
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
    ConversationPointPersonalStateAPIView,
    ConversationPointResponseAPIView,
    ConversationPointCloseResponsesAPIView,
    ConversationPointResolveAPIView,
)


from .participant_api import (
    ConversationIdentitySearchAPIView, ConversationParticipantsAPIView,
    ConversationInviteIdentifierAPIView, ConversationRemoveParticipationAPIView,
    ConversationCancelInvitationAPIView, ConversationCollectiveRevokeAPIView,
    ConversationCollectiveInboxAPIView, ConversationCollectiveRespondAPIView,
    ConversationSelfEntryAPIView, ConversationJoinRequestsAPIView,
    ConversationJoinRequestDecisionAPIView,
    ConversationWithdrawJoinRequestAPIView,
)


app_name = "conversations-api"

urlpatterns = [
    path("realtime-ticket/", ConversationRealtimeTicketAPIView.as_view(), name="realtime-ticket"),
    path("points/<uuid:point_pk>/entries/sync/", ConversationEntrySyncAPIView.as_view(), name="entry-sync"),
    path("points/<uuid:point_pk>/entries/search/", ConversationEntrySearchAPIView.as_view(), name="entry-search"),
    path("points/<uuid:point_pk>/receipts/", ConversationEntryReceiptsAPIView.as_view(), name="entry-receipts"),
    path("points/<uuid:point_pk>/mentions/", ConversationEntryMentionCandidatesAPIView.as_view(), name="entry-mentions"),
    path("points/<uuid:point_pk>/references/options/", ConversationEntryReferenceOptionsAPIView.as_view(), name="entry-reference-options"),
    path("references/<uuid:reference_pk>/", ConversationEntryReferenceAPIView.as_view(), name="entry-reference"),
    path("references/<uuid:reference_pk>/file/", ConversationEntryReferenceFileAPIView.as_view(), name="entry-reference-file"),
    path("entries/<uuid:entry_pk>/", ConversationEntryDetailAPIView.as_view(), name="entry-detail"),
    path("entries/<uuid:entry_pk>/reactions/", ConversationEntryReactionAPIView.as_view(), name="entry-reactions"),
    path("", ConversationListAPIView.as_view(), name="list"),
    path("attention-presence/", ConversationAttentionPresenceAPIView.as_view(), name="attention-presence"),
    path("by-context/<str:kind>/<str:context_pk>/", ConversationContextLookupAPIView.as_view(), name="by-context"),
    path("by-context/<str:kind>/<str:context_pk>/ensure/", ConversationContextEnsureAPIView.as_view(), name="context-ensure"),
    path("<uuid:pk>/", ConversationDetailAPIView.as_view(), name="detail"),
    path("<uuid:pk>/attention/", ConversationAttentionAPIView.as_view(), name="attention"),
    path("<uuid:pk>/candidates/", ConversationIdentitySearchAPIView.as_view(), name="identity-search"),
    path("<uuid:pk>/participants/", ConversationParticipantsAPIView.as_view(), name="participants"),
    path("<uuid:pk>/invite/", ConversationInviteIdentifierAPIView.as_view(), name="invite-identifier"),
    path("<uuid:pk>/participants/<uuid:participation_pk>/remove/", ConversationRemoveParticipationAPIView.as_view(), name="participant-remove"),
    path("<uuid:pk>/invitations/<uuid:invitation_pk>/cancel/", ConversationCancelInvitationAPIView.as_view(), name="invite-cancel"),
    path("<uuid:pk>/collectives/<uuid:access_pk>/revoke/", ConversationCollectiveRevokeAPIView.as_view(), name="collective-revoke"),
    path("collective-invitations/", ConversationCollectiveInboxAPIView.as_view(), name="collective-inbox"),
    path("collective-invitations/<uuid:access_pk>/respond/", ConversationCollectiveRespondAPIView.as_view(), name="collective-respond"),
    path("<uuid:pk>/entry/", ConversationSelfEntryAPIView.as_view(), name="self-entry"),
    path("join-requests/<uuid:join_request_pk>/withdraw/", ConversationWithdrawJoinRequestAPIView.as_view(), name="join-withdraw"),
    path("<uuid:pk>/join-requests/", ConversationJoinRequestsAPIView.as_view(), name="join-requests"),
    path("<uuid:pk>/join-requests/<uuid:join_request_pk>/decide/", ConversationJoinRequestDecisionAPIView.as_view(), name="join-decision"),

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
    path("points/<uuid:point_pk>/close-responses/", ConversationPointCloseResponsesAPIView.as_view(), name="point-close-responses"),
    path("points/<uuid:point_pk>/resolve/", ConversationPointResolveAPIView.as_view(), name="point-resolve"),
    path("points/<uuid:point_pk>/reply-media/", ConversationPointMediaResponseAPIView.as_view(), name="point-reply-media"),
    path("points/<uuid:point_pk>/acknowledge/", ConversationPointAcknowledgeAPIView.as_view(), name="point-acknowledge"),
    path("points/<uuid:point_pk>/personal-state/", ConversationPointPersonalStateAPIView.as_view(), name="point-personal-state"),
    path("invitations/", ConversationInvitationListAPIView.as_view(), name="invitation-list"),
    path("invitations/<uuid:invitation_pk>/respond/", ConversationInvitationRespondAPIView.as_view(), name="invitation-respond"),
]

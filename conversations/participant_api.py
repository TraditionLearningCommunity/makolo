"""Private, owner-checked Conversation participant and invitation endpoints."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, views
from rest_framework.exceptions import ValidationError as DRFValidationError, NotFound
from rest_framework.response import Response

from core.api.privacy import PrivateNoStoreMixin

from .collective_models import ConversationCollectiveAccess, ConversationCollectiveStatus
from .core_models import (
    Conversation, ConversationInvitation, ConversationInvitationStatus,
    ConversationJoinRequest, ConversationParticipation,
)
from .detail_presentation import conversation_members_for_profile
from .participant_services import (
    answer_collective_invitation, collective_invitation_inbox,
    conversation_collectives_for_manager, invite_identifier,
    revoke_collective_access, search_invitation_candidates,
)
from .services import (
    can_manage_conversation, can_view_conversation, create_join_request,
    join_conversation, leave_conversation, remove_participation,
    respond_to_join_request,
)


def _existing_conversation(pk):
    return get_object_or_404(
        Conversation.objects.select_related("context"), pk=pk,
    )


def _manageable(actor, pk):
    conversation = _existing_conversation(pk)
    if not can_manage_conversation(actor, conversation):
        raise NotFound("Conversation inaccessible.")
    return conversation


def _visible(actor, pk):
    conversation = _existing_conversation(pk)
    if not can_view_conversation(actor, conversation):
        raise NotFound("Conversation inaccessible.")
    return conversation


def _error(exc):
    if isinstance(exc, PermissionDenied):
        raise PermissionDenied(str(exc))
    return Response({
        "errors": exc.message_dict if hasattr(exc, "message_dict")
        else exc.messages,
    }, status=400)


class ConversationIdentitySearchAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _manageable(request.user, pk)
        query = request.query_params.get("q", "")
        if not isinstance(query, str) or len(query) > 80:
            raise DRFValidationError({"q": "Recherche trop longue."})
        return Response({
            "results": search_invitation_candidates(
                actor=request.user, conversation=conversation, query=query,
            ),
            "identity_rule": "Seul l'identifiant Makolo sélectionné peut être invité.",
        })


class ConversationParticipantsAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible(request.user, pk)
        managed = can_manage_conversation(request.user, conversation)
        return Response({
            "members": conversation_members_for_profile(request.user, conversation),
            "collectives": conversation_collectives_for_manager(
                request.user, conversation,
            ) if managed else [],
            "can_manage": managed,
            "can_leave": ConversationParticipation.objects.filter(
                conversation=conversation, profile=request.user,
                status="active",
            ).exists(),
        })


class ConversationInviteIdentifierAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = _manageable(request.user, pk)
        kind = request.data.get("kind")
        identifier = request.data.get("identifier")
        reference = request.data.get("client_reference")
        if reference is not None and (
            not isinstance(reference, str) or len(reference) > 80
        ):
            raise DRFValidationError({"client_reference": "Référence invalide."})
        try:
            result_kind, item = invite_identifier(
                actor=request.user, conversation=conversation, kind=kind,
                identifier=identifier, client_reference=reference,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({
            "id": str(item.pk), "kind": result_kind, "status": item.status,
            "identifier": identifier if isinstance(identifier, str) else "",
            "requires_acceptance": item.status == "pending",
        })


class ConversationRemoveParticipationAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, participation_pk):
        conversation = _manageable(request.user, pk)
        participation = get_object_or_404(
            ConversationParticipation, pk=participation_pk,
            conversation=conversation,
        )
        try:
            record = remove_participation(actor=request.user, participation=participation)
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(record.pk), "status": record.status})


class ConversationCancelInvitationAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, invitation_pk):
        conversation = _manageable(request.user, pk)
        from django.db import transaction
        from django.utils import timezone
        with transaction.atomic():
            invitation = get_object_or_404(
                ConversationInvitation.objects.select_for_update(),
                pk=invitation_pk, conversation=conversation,
            )
            if invitation.status == ConversationInvitationStatus.PENDING:
                invitation.status = ConversationInvitationStatus.CANCELLED
                invitation.responded_at = timezone.now()
                invitation.save(update_fields=["status", "responded_at", "updated_at"])
        return Response({"id": str(invitation.pk), "status": invitation.status})


class ConversationCollectiveRevokeAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, access_pk):
        conversation = _existing_conversation(pk)
        access = get_object_or_404(
            ConversationCollectiveAccess, pk=access_pk,
            conversation=conversation,
        )
        try:
            access = revoke_collective_access(actor=request.user, access=access)
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(access.pk), "status": access.status})


class ConversationCollectiveInboxAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            "results": [
                {
                    "id": str(item.pk), "conversation_id": str(item.conversation_id),
                    "kind": "space" if item.space_id else "group",
                    "identifier": item.space.slug if item.space_id else item.group.slug,
                    "label": item.space.name if item.space_id else item.group.name,
                    "status": item.status, "created_at": item.created_at,
                    "expires_at": item.expires_at,
                }
                for item in collective_invitation_inbox(request.user)
            ],
        })


class ConversationCollectiveRespondAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, access_pk):
        if request.data.get("decision") not in {"accept", "decline"}:
            raise DRFValidationError({"decision": "Choisissez accept ou decline."})
        link = get_object_or_404(ConversationCollectiveAccess, pk=access_pk)
        try:
            link = answer_collective_invitation(
                actor=request.user, access=link,
                accept=request.data["decision"] == "accept",
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({
            "id": str(link.pk), "status": link.status,
            "conversation_id": str(link.conversation_id),
        })


class ConversationSelfEntryAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = _existing_conversation(pk)
        decision = request.data.get("action")
        if decision not in {"join", "request", "leave"}:
            raise DRFValidationError({"action": "Action invalide."})
        try:
            if decision == "join":
                outcome = join_conversation(actor=request.user, conversation=conversation)
            elif decision == "request":
                outcome = create_join_request(
                    actor=request.user, conversation=conversation,
                    client_reference=request.data.get("client_reference"),
                )
            else:
                if not can_view_conversation(request.user, conversation):
                    raise PermissionDenied("Conversation inaccessible.")
                outcome = leave_conversation(actor=request.user, conversation=conversation)
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(outcome.pk), "status": outcome.status})


class ConversationJoinRequestsAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _manageable(request.user, pk)
        qs = ConversationJoinRequest.objects.filter(
            conversation=conversation, status="pending",
        ).select_related("requester").order_by("created_at")[:50]
        return Response({
            "results": [
                {
                    "id": str(item.pk), "identifier": item.requester.username,
                    # The requester intentionally supplies her Makolo handle;
                    # a private full name is not implied by the join request.
                    "label": item.requester.username,
                    "status": item.status,
                }
                for item in qs
            ],
        })


class ConversationJoinRequestDecisionAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, join_request_pk):
        conversation = _manageable(request.user, pk)
        if request.data.get("decision") not in {"approve", "reject"}:
            raise DRFValidationError({"decision": "Décision invalide."})
        join_request = get_object_or_404(
            ConversationJoinRequest, pk=join_request_pk, conversation=conversation,
        )
        try:
            resolved = respond_to_join_request(
                actor=request.user, join_request=join_request,
                approve=request.data["decision"] == "approve",
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(resolved.pk), "status": resolved.status})

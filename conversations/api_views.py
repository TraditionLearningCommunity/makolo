from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, views
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response

from .core_models import Conversation, ConversationInvitation, ConversationInvitationStatus
from .point_models import ConversationPoint, ConversationPointResponseMode
from .point_services import acknowledge_point, point_response_allowed, point_visible_to, submit_point_response
from .presentation import (
    conversation_context_label,
    conversation_rows_for_profile,
    now_points_for_profile,
    search_conversations_for_profile,
)
from .services import can_view_conversation, respond_to_conversation_invitation


MAX_PAGE_SIZE = 100


def _bounded_limit(request, default=50):
    try:
        return min(max(int(request.query_params.get("limit", default)), 1), MAX_PAGE_SIZE)
    except (TypeError, ValueError) as exc:
        raise DRFValidationError({"limit": "limit doit être un entier entre 1 et 100."}) from exc


def _resolution_summary(point):
    if point.lifecycle != "resolved":
        return ""
    try:
        return point.resolution.summary or ""
    except Exception:
        return ""


def _serialize_point(point, *, profile, reason=None, section=None):
    return {
        "id": str(point.pk),
        "conversation_id": str(point.conversation_id),
        "kind": point.kind,
        "response_mode": point.response_mode,
        "lifecycle": point.lifecycle,
        "importance": point.importance,
        "title": point.title,
        "body": point.body,
        "requires_acknowledgement": point.requires_acknowledgement,
        "opens_at": point.opens_at,
        "deadline_at": point.deadline_at,
        "valid_until": point.valid_until,
        "can_respond": point_response_allowed(profile, point),
        "attention_reason": reason,
        "section": section,
        "resolution_summary": _resolution_summary(point),
        "published_at": point.published_at,
        "updated_at": point.updated_at,
    }


def _serialize_conversation_row(row):
    conversation = row.conversation
    return {
        "id": str(conversation.pk),
        "title": conversation.title_override or row.context_label,
        "purpose": conversation.purpose,
        "lifecycle": conversation.lifecycle,
        "context": {"kind": conversation.context.kind, "label": row.context_label},
        "attention_count": row.attention_count,
        "latest_result": row.latest_result,
        "all_clear": row.all_clear,
        "updated_at": conversation.updated_at,
    }


def _visible_conversation_or_404(profile, pk):
    conversation = get_object_or_404(Conversation.objects.select_related("context"), pk=pk)
    if not can_view_conversation(profile, conversation):
        raise NotFound("Conversation introuvable.")
    return conversation


def _visible_point_or_404(profile, pk):
    point = get_object_or_404(
        ConversationPoint.objects.select_related(
            "conversation",
            "conversation__context",
            "visibility_audience",
            "response_audience",
            "expected_action_audience",
            "resolution_audience",
        ),
        pk=pk,
    )
    if not point_visible_to(profile, point):
        raise NotFound("Point introuvable.")
    return point


def _service_error(exc):
    if isinstance(exc, PermissionDenied):
        return Response({"detail": "Action non autorisée."}, status=status.HTTP_403_FORBIDDEN)
    if hasattr(exc, "message_dict"):
        return Response({"errors": exc.message_dict}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"errors": getattr(exc, "messages", [str(exc)])}, status=status.HTTP_400_BAD_REQUEST)


class ConversationListAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = _bounded_limit(request)
        q = (request.query_params.get("q") or "").strip()[:120]
        updated_after_raw = (request.query_params.get("updated_after") or "").strip()
        updated_after = parse_datetime(updated_after_raw) if updated_after_raw else None
        if updated_after_raw and updated_after is None:
            raise DRFValidationError({"updated_after": "Date/heure ISO invalide."})

        if q:
            seen = set()
            payload = []
            for result in search_conversations_for_profile(request.user, q, limit=limit * 2):
                conversation = result.conversation
                if conversation.pk in seen:
                    continue
                if updated_after and conversation.updated_at <= updated_after:
                    continue
                seen.add(conversation.pk)
                payload.append({
                    "id": str(conversation.pk),
                    "title": conversation.title_override or result.context_label,
                    "purpose": conversation.purpose,
                    "lifecycle": conversation.lifecycle,
                    "context": {"kind": conversation.context.kind, "label": result.context_label},
                    "matched_point_id": str(result.point.pk) if result.point else None,
                    "updated_at": conversation.updated_at,
                })
                if len(payload) >= limit:
                    break
            return Response({"results": payload, "count": len(payload)})

        rows = conversation_rows_for_profile(request.user, only_attention=False, limit=limit * 2)
        if updated_after:
            rows = [row for row in rows if row.conversation.updated_at > updated_after]
        rows = rows[:limit]
        return Response({"results": [_serialize_conversation_row(row) for row in rows], "count": len(rows)})


class ConversationDetailAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        rows = now_points_for_profile(request.user, conversation, limit=_bounded_limit(request))
        label = conversation_context_label(conversation, request.user)
        return Response({
            "id": str(conversation.pk),
            "title": conversation.title_override or label,
            "purpose": conversation.purpose,
            "lifecycle": conversation.lifecycle,
            "context": {"kind": conversation.context.kind, "label": label},
            "points": [
                _serialize_point(item["point"], profile=request.user, reason=item["reason"], section=item["section"])
                for item in rows
            ],
            "updated_at": conversation.updated_at,
        })


class ConversationPointResponseAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        value = request.data.get("value")
        if point.response_mode == ConversationPointResponseMode.MULTIPLE_CHOICE and not isinstance(value, list):
            raise DRFValidationError({"value": "Une liste de choix est attendue."})
        try:
            point_response = submit_point_response(
                actor=request.user,
                point=point,
                value=value,
                client_reference=request.data.get("client_reference") or None,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _service_error(exc)
        return Response({
            "id": str(point_response.pk),
            "point_id": str(point_response.point_id),
            "status": point_response.status,
            "value": point_response.value,
            "submitted_at": point_response.submitted_at,
        })


class ConversationPointAcknowledgeAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        try:
            state = acknowledge_point(actor=request.user, point=point)
        except (ValidationError, PermissionDenied) as exc:
            return _service_error(exc)
        return Response({"point_id": str(point.pk), "acknowledged_at": state.acknowledged_at})


class ConversationInvitationListAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        invitations = list(
            ConversationInvitation.objects.filter(
                invitee=request.user,
                status=ConversationInvitationStatus.PENDING,
            )
            .select_related("conversation", "conversation__context")
            .order_by("created_at", "id")[:_bounded_limit(request)]
        )
        return Response({
            "results": [
                {
                    "id": str(invitation.pk),
                    "conversation_id": str(invitation.conversation_id),
                    "status": invitation.status,
                    "expires_at": invitation.expires_at,
                    "created_at": invitation.created_at,
                }
                for invitation in invitations
            ],
            "count": len(invitations),
        })


class ConversationInvitationRespondAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_pk):
        invitation = get_object_or_404(
            ConversationInvitation.objects.select_related("conversation", "conversation__context"),
            pk=invitation_pk,
            invitee=request.user,
        )
        decision = request.data.get("decision")
        if decision not in {"accept", "decline"}:
            raise DRFValidationError({"decision": "Utilisez accept ou decline."})
        try:
            invitation = respond_to_conversation_invitation(
                actor=request.user,
                invitation=invitation,
                accept=decision == "accept",
            )
        except (ValidationError, PermissionDenied) as exc:
            return _service_error(exc)
        return Response({
            "id": str(invitation.pk),
            "conversation_id": str(invitation.conversation_id),
            "status": invitation.status,
            "responded_at": invitation.responded_at,
        })

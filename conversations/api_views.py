from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from uuid import UUID
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, views
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response

from core.api.privacy import PrivateNoStoreMixin
from organizations.models import Organization

from .attention import has_conversation_attention
from .composing import can_ensure_context_conversation, composer_capabilities, contribute_text, publish_composed_point
from .core_models import Conversation, ConversationContext, ConversationContextKind, ConversationInvitation, ConversationInvitationStatus
from .point_models import ConversationPoint, ConversationPointResponseMode
from .point_services import acknowledge_point, point_response_allowed, point_visible_to, submit_point_response
from .presentation import (
    conversation_context_label,
    conversations_for_context,
    conversation_rows_for_profile,
    essential_points_for_profile,
    now_points_for_profile,
    other_visible_points_for_profile,
    search_conversations_for_profile,
)
from .services import (
    can_view_conversation,
    respond_to_conversation_invitation,
    update_personal_conversation_state,
    ensure_context_conversation,
)


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
        "can_respond": (
            point.lifecycle == "open"
            and (point.opens_at is None or point.opens_at <= timezone.now())
            and (point.deadline_at is None or point.deadline_at > timezone.now())
            and (point.valid_until is None or point.valid_until > timezone.now())
            and point_response_allowed(profile, point)
        ),
        "options": [
            {"id": str(option.pk), "label": option.label}
            for option in point.options.all()
        ],
        "exchange_preview": [
            {"id": str(entry.pk), "body": entry.body, "created_at": entry.created_at}
            for entry in reversed(list(point.exchange_entries.filter(
                moderation_state="visible",
            ).order_by("-created_at", "-pk")[:5]))
        ] if point.kind == "exchange" else [],
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


class ConversationContextLookupAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, kind, context_pk):
        conversations = conversations_for_context(request.user, kind, context_pk)
        return Response({
            "count": len(conversations),
            "can_ensure": can_ensure_context_conversation(request.user, kind, context_pk),
            "results": [
                {
                    "id": str(item.pk),
                    "title": item.title_override or conversation_context_label(item, request.user),
                    "purpose": item.purpose,
                    "context": {
                        "kind": item.context.kind,
                        "label": conversation_context_label(item, request.user),
                    },
                    "updated_at": item.updated_at,
                }
                for item in conversations
            ],
        })


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


class ConversationAttentionPresenceAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"has_attention": has_conversation_attention(request.user)})


class ConversationListAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = _bounded_limit(request)
        q = (request.query_params.get("q") or "").strip()[:120]
        updated_after_raw = (request.query_params.get("updated_after") or "").strip()
        updated_after = parse_datetime(updated_after_raw) if updated_after_raw else None
        if updated_after_raw and (
            updated_after is None or timezone.is_naive(updated_after)
        ):
            raise DRFValidationError({
                "updated_after": "Date/heure ISO avec fuseau horaire attendue.",
            })

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


class ConversationDetailAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        limit = _bounded_limit(request)
        rows = now_points_for_profile(request.user, conversation, limit=limit)
        active_ids = {item["point"].pk for item in rows}
        essential = [
            point for point in essential_points_for_profile(request.user, conversation, limit=limit)
            if point.pk not in active_ids
        ]
        seen = active_ids | {point.pk for point in essential}
        elsewhere = other_visible_points_for_profile(
            request.user, conversation, excluded_ids=seen, limit=limit,
        )
        seen.update(point.pk for point in elsewhere)
        focused_point = None
        focused_raw = (request.query_params.get("focus_point") or "").strip()
        if focused_raw:
            try:
                focused_id = UUID(focused_raw)
            except (ValueError, AttributeError):
                raise DRFValidationError({"focus_point": "Point invalide."})
            focused = ConversationPoint.objects.filter(
                pk=focused_id, conversation=conversation,
            ).select_related("visibility_audience", "response_audience", "resolution_audience").prefetch_related("options").first()
            if focused and point_visible_to(request.user, focused):
                if focused.pk not in seen:
                    focused_point = _serialize_point(focused, profile=request.user, section="focus")
        label = conversation_context_label(conversation, request.user)
        state = conversation.user_states.filter(profile=request.user).first()
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
            "essential": [
                _serialize_point(point, profile=request.user, section="essential")
                for point in essential
            ],
            "elsewhere": [
                _serialize_point(point, profile=request.user, section="elsewhere")
                for point in elsewhere
            ],
            "focused_point": focused_point,
            "composer": composer_capabilities(request.user, conversation),
            "personal_state": {
                "muted": bool(state and state.muted_at),
                "hidden": bool(state and state.hidden_at),
                "archived": bool(state and state.archived_at),
                "pinned": bool(state and state.pinned_at),
                "revisit": bool(state and state.revisit_at),
            },
            "updated_at": conversation.updated_at,
        })



def _represented_space_from_request(request):
    raw = request.data.get("represented_space_id")
    if raw in (None, ""):
        return None
    try:
        return Organization.objects.get(pk=raw)
    except (Organization.DoesNotExist, ValidationError, ValueError, TypeError) as exc:
        raise PermissionDenied("Espace non autorisé.") from exc


class ConversationComposeAPIView(PrivateNoStoreMixin, views.APIView):
    """Owner-confirmed Point publication or contribution to an existing Exchange."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        mode = (request.data.get("mode") or "text").strip()
        client_ref = request.data.get("client_reference")
        represented_space = _represented_space_from_request(request)
        try:
            if mode == "text":
                outcome, result, point_id = contribute_text(
                    actor=request.user, conversation=conversation,
                    body=request.data.get("body"),
                    point_id=request.data.get("point_id"),
                    client_reference=client_ref, represented_space=represented_space,
                    audience_id=request.data.get("audience_id"),
                )
                return Response({"kind": outcome, "id": str(result.pk), "point_id": str(point_id)})
            if mode == "point":
                point = publish_composed_point(
                    actor=request.user, conversation=conversation,
                    kind=request.data.get("kind"), title=request.data.get("title", ""),
                    body=request.data.get("body", ""), options=request.data.get("options"),
                    audience_id=request.data.get("audience_id"),
                    represented_space=represented_space, client_reference=client_ref,
                )
                return Response({"kind": "point", "id": str(point.pk), "point_id": str(point.pk)})
            raise DRFValidationError({"mode": "Mode de composition inconnu."})
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)


class ConversationExchangeEntryAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        try:
            outcome, entry, point_id = contribute_text(
                actor=request.user, conversation=point.conversation,
                body=request.data.get("body"), point_id=str(point.pk),
                represented_space=_represented_space_from_request(request),
                client_reference=request.data.get("client_reference"),
            )
            return Response({"kind": outcome, "id": str(entry.pk), "point_id": str(point_id)})
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)


class ConversationContextEnsureAPIView(PrivateNoStoreMixin, views.APIView):
    """Open a permitted contextual Conversation; never infer direct consent."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, kind, context_pk):
        if kind == ConversationContextKind.DIRECT or kind not in ConversationContext.TARGET_FIELDS:
            raise PermissionDenied("Une Conversation directe exige un consentement existant.")
        field = ConversationContext.TARGET_FIELDS[kind][0]
        related_model = ConversationContext._meta.get_field(field).remote_field.model
        try:
            target = related_model.objects.get(pk=context_pk)
        except (related_model.DoesNotExist, ValidationError, ValueError, TypeError):
            raise NotFound("Contexte introuvable.")
        try:
            conversation = ensure_context_conversation(
                actor=request.user, kind=kind, **{field: target},
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)
        if not can_view_conversation(request.user, conversation):
            raise NotFound("Conversation introuvable.")
        return Response({"id": str(conversation.pk)})


class ConversationPointResponseAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        value = request.data.get("value")
        if point.response_mode == ConversationPointResponseMode.MULTIPLE_CHOICE and not isinstance(value, list):
            raise DRFValidationError({"value": "Une liste de choix est attendue."})
        represented_space = None
        represented_space_id = request.data.get("represented_space_id")
        if represented_space_id:
            represented_space = Organization.objects.filter(pk=represented_space_id).first()
            if represented_space is None:
                raise DRFValidationError({"represented_space_id": "Espace introuvable."})
        try:
            point_response = submit_point_response(
                actor=request.user,
                point=point,
                value=value,
                represented_space=represented_space,
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


class ConversationPersonalStateAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        allowed = {"mute", "hidden", "archived", "pinned", "revisit"}
        unknown = set(request.data) - allowed
        if unknown:
            raise DRFValidationError({"detail": "État Conversation inconnu."})
        try:
            state = update_personal_conversation_state(
                actor=request.user,
                conversation=conversation,
                mute=request.data.get("mute") if "mute" in request.data else None,
                hidden=request.data.get("hidden") if "hidden" in request.data else None,
                archived=request.data.get("archived") if "archived" in request.data else None,
                pinned=request.data.get("pinned") if "pinned" in request.data else None,
                revisit=request.data.get("revisit") if "revisit" in request.data else None,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _service_error(exc)
        return Response({
            "conversation_id": str(conversation.pk),
            "muted": bool(state.muted_at),
            "hidden": bool(state.hidden_at),
            "archived": bool(state.archived_at),
            "pinned": bool(state.pinned_at),
            "revisit": bool(state.revisit_at),
        })


class ConversationPointAcknowledgeAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        try:
            state = acknowledge_point(actor=request.user, point=point)
        except (ValidationError, PermissionDenied) as exc:
            return _service_error(exc)
        return Response({"point_id": str(point.pk), "acknowledged_at": state.acknowledged_at})


class ConversationInvitationListAPIView(PrivateNoStoreMixin, views.APIView):
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


class ConversationInvitationRespondAPIView(PrivateNoStoreMixin, views.APIView):
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

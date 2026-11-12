from __future__ import annotations

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from uuid import UUID
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, views
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from core.api.privacy import PrivateNoStoreMixin
from organizations.models import Organization

from .attention import has_conversation_attention
from .attention_projection import conversation_attention_sections
from .point_interactions import point_interactions_for_profile
from .participant_services import (
    collective_invitation_inbox, invitation_accept_allowed,
    collective_invitation_accept_allowed,
)
from .participation_inbox import participation_inbox_for_profile
from .detail_presentation import conversation_detail_extra_for_profile
from .history import page_points_for_profile, point_personal_result
from .timeline import recent_timeline_for_profile, timeline_presentation
from .composing import can_ensure_context_conversation, composer_capabilities, contribute_text, publish_composed_point
from .core_models import Conversation, ConversationContext, ConversationContextKind, ConversationInvitation, ConversationInvitationStatus
from .point_models import ConversationPoint, ConversationPointResponseMode
from .form_services import form_request_for_profile
from .media_services import attachment_for_download, can_download_attachment
from .semantic_media import publish_semantic_point_with_media, response_media_label
from .rich_services import (
    available_form_versions, can_prepare_form, publish_conversation_form,
    readable_exchange_entries, serialize_attachment, upload_conversation_media,
    visible_attachments_for_profile,
    submit_point_media_response,
)
from .point_services import (
    acknowledge_point, update_point_personal_state,
    close_point_responses, point_response_allowed,
    point_visible_to, point_resolution_visible_to, resolve_point, submit_point_response,
)
from .presentation import (
    conversation_context_label,
    conversations_for_context,
    conversation_rows_for_profile,
    essential_points_for_profile,
    now_points_for_profile,
    other_visible_points_for_profile,
    search_conversations_for_profile,
    visible_exchange_entries_for_profile,
)
from .services import (
    can_view_conversation,
    respond_to_conversation_invitation,
    update_personal_conversation_state,
    ensure_context_conversation,
)


MAX_PAGE_SIZE = 100



def _request_boolean(request, key, default=False):
    value = request.data.get(key, default)
    if value is True or value is False:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0", ""}:
            return False
    raise DRFValidationError({key: "Valeur booléenne invalide."})


def _bounded_limit(request, default=50):
    try:
        return min(max(int(request.query_params.get("limit", default)), 1), MAX_PAGE_SIZE)
    except (TypeError, ValueError) as exc:
        raise DRFValidationError({"limit": "limit doit être un entier entre 1 et 100."}) from exc


def _resolution_summary(point, profile):
    if point.lifecycle != "resolved" or not point_resolution_visible_to(profile, point):
        return ""
    try:
        return point.resolution.summary or ""
    except Exception:
        return ""


def _serialize_point(point, *, profile, reason=None, section=None):
    interactions = point_interactions_for_profile(profile, point)
    timeline_state = timeline_presentation(profile, point, interactions=interactions)
    linked_form = form_request_for_profile(point, profile) if point.kind == "form_request" else None
    prior = point.supersedes if point.supersedes_id else None
    successor = (
        point.superseded_by_points.order_by("-published_at", "-created_at").first()
        if point.lifecycle == "superseded" else None
    )
    visible_media = [
        item for item in visible_attachments_for_profile(profile, point, limit=100)
        if item.exchange_entry_id is None
    ]
    response_media = {}
    response_labels = {}
    for item in visible_media:
        if item.response_id:
            key = str(item.response_id)
            response_media.setdefault(key, []).append(serialize_attachment(item))
            response_labels[key] = response_media_label(point, item.response)
    return {
        "id": str(point.pk),
        "conversation_id": str(point.conversation_id),
        "kind": point.kind,
        "client_reference": (
            point.client_reference if point.published_by_id == profile.pk else None
        ),
        # Identity only for an already-authorized Point. No account IDs,
        # contact details or private Profile fields escape this projection.
        "author": {
            # A Space is a context of representation, never the human author.
            # Preserve the existing public-identifier policy for other users;
            # the full name remains restricted to the requesting Profile.
            "label": (
                (
                    point.published_by.get_full_name().strip()
                    if point.published_by_id == profile.pk else ""
                )
                or point.published_by.username
                or "Participant"
            ),
            "is_mine": point.published_by_id == profile.pk,
            "represented_space": bool(point.represented_space_id),
            "space_label": (
                point.represented_space.name
                if point.represented_space_id else None
            ),
        },
        "response_mode": point.response_mode,
        "lifecycle": point.lifecycle,
        "timeline_compact": timeline_state["compact"],
        "timeline_summary": timeline_state["summary"],
        "response_status": point_personal_result(profile, point),
        "my_response": interactions["my_response"],
        "response_hint": interactions["response_hint"],
        "response_window_open": interactions["response_window_open"],
        "represented_responses": interactions["represented_responses"],
        "poll_results": interactions["poll_results"],
        "acknowledged": interactions["acknowledged"],
        "revisit": interactions["revisit"],
        "can_acknowledge": interactions["can_acknowledge"],
        "can_close_responses": interactions["can_close_responses"],
        "can_resolve": interactions["can_resolve"],
        "can_change_response": point.allow_response_change,
        "supersedes_point_id": (
            str(prior.pk) if prior is not None and point_visible_to(profile, prior) else None
        ),
        "replaced_by_point_id": (
            str(successor.pk) if successor is not None
            and point_visible_to(profile, successor) else None
        ),
        "importance": point.importance,
        "title": point.title,
        "body": point.body,
        "requires_acknowledgement": point.requires_acknowledgement,
        "opens_at": point.opens_at,
        "deadline_at": point.deadline_at,
        "valid_until": point.valid_until,
        "can_respond": interactions["can_respond"],
        "options": [
            {
                "id": str(option.pk), "label": option.label,
                "attachments": [
                    serialize_attachment(media)
                    for media in visible_media if media.option_id == option.pk
                ],
            }
            for option in point.options.all()
        ],
        "exchange_preview": [
            {
                "id": str(entry.pk), "body": entry.body,
                "created_at": entry.created_at, "own": entry.author_id == profile.pk,
                "client_reference": (
                    entry.client_reference if entry.author_id == profile.pk else None
                ),
                "attachments": [
                    serialize_attachment(item)
                    for item in entry.attachments.all() if can_download_attachment(profile, item)
                ],
            }
            for entry in visible_exchange_entries_for_profile(profile, point, limit=5)
        ] if point.kind == "exchange" else [],
        # The Point, each Poll assertion, and each Response retain their
        # own media order. Clients must not append all files at the bottom.
        "attachments": [
            serialize_attachment(item) for item in visible_media
            if item.response_id is None and item.option_id is None
        ],
        "response_media": [
            {
                "response_id": key, "label": response_labels.get(key, ""),
                "attachments": files,
            }
            for key, files in response_media.items()
        ],
        "form_request": ({
            "id": str(linked_form.pk), "status": linked_form.status,
            "links": {
                "detail": f"api/v1/questionnaires/requests/{linked_form.pk}/",
                "save": f"api/v1/questionnaires/requests/{linked_form.pk}/save/",
                "submit": f"api/v1/questionnaires/requests/{linked_form.pk}/submit/",
            },
        } if linked_form is not None else None),
        "attention_reason": reason,
        "section": section,
        "resolution_summary": _resolution_summary(point, profile),
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
        "card": row.card,
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


class ConversationAttentionAPIView(PrivateNoStoreMixin, views.APIView):
    """The current action lens; not a second Point feed or a notification store."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        return Response(conversation_attention_sections(request.user, conversation))


class ConversationListAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = _bounded_limit(request)
        tab = (request.query_params.get("tab") or "all").strip().lower()
        if tab not in {"all", "for-me", "archived"}:
            raise DRFValidationError({"tab": "Filtre inconnu."})
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
            attention_by_conversation = (
                {
                    row.conversation.pk: row.attention_count
                    for row in conversation_rows_for_profile(
                        request.user, only_attention=True, limit=300,
                    )
                } if tab == "for-me" else {}
            )
            seen = set()
            payload = []
            for result in search_conversations_for_profile(
                request.user, q, limit=limit * 2, include_archived=tab == "archived",
            ):
                conversation = result.conversation
                if conversation.pk in seen:
                    continue
                if tab == "for-me" and conversation.pk not in attention_by_conversation:
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
                    "attention_count": attention_by_conversation.get(conversation.pk, 0),
                    "card": {
                        **result.card,
                        "attention_count": attention_by_conversation.get(conversation.pk, 0),
                    },
                    "updated_at": conversation.updated_at,
                })
                if len(payload) >= limit:
                    break
            return Response({"results": payload, "count": len(payload)})

        rows = conversation_rows_for_profile(
            request.user,
            archived=tab == "archived",
            only_attention=tab == "for-me",
            limit=limit * 2,
        )
        if updated_after:
            rows = [row for row in rows if row.conversation.updated_at > updated_after]
        rows = rows[:limit]
        return Response({"results": [_serialize_conversation_row(row) for row in rows], "count": len(rows)})


class ConversationPointsDepthAPIView(PrivateNoStoreMixin, views.APIView):
    """Search and stable-keyset history of real Points; never a chat timeline."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        try:
            page = page_points_for_profile(
                request.user, conversation,
                query=request.query_params.get("q", ""),
                section=request.query_params.get("section", "history"),
                cursor=request.query_params.get("cursor") or None,
                limit=request.query_params.get("limit", 25),
            )
        except ValidationError as exc:
            return _service_error(exc)
        return Response({
            "results": [
                {
                    **_serialize_point(point, profile=request.user, section="history"),
                }
                for point in page["results"]
            ],
            "next_cursor": page["next_cursor"],
            "section": request.query_params.get("section", "history"),
        })


class ConversationDetailAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        limit = _bounded_limit(request)
        visibility_cache, audience_cache, history_cache = {}, {}, {}
        attention_caches = ({}, {}, {})
        rows = now_points_for_profile(
            request.user, conversation, limit=limit,
            visibility_cache=visibility_cache, audience_cache=audience_cache,
            history_cache=history_cache, attention_caches=attention_caches,
        )
        active_ids = {item["point"].pk for item in rows}
        essential = [
            point for point in essential_points_for_profile(request.user, conversation, limit=limit)
            if point.pk not in active_ids
        ]
        seen = active_ids | {point.pk for point in essential}
        elsewhere = other_visible_points_for_profile(
            request.user, conversation, excluded_ids=seen, limit=limit,
            visibility_cache=visibility_cache, audience_cache=audience_cache,
            history_cache=history_cache,
        )
        seen.update(point.pk for point in elsewhere)
        timeline = recent_timeline_for_profile(request.user, conversation)
        visible_timeline_ids = {point.pk for point in timeline["points"]}
        focused_point = None
        focused_raw = (request.query_params.get("focus_point") or "").strip()
        if focused_raw:
            try:
                focused_id = UUID(focused_raw)
            except (ValueError, AttributeError):
                raise DRFValidationError({"focus_point": "Point invalide."})
            focused = ConversationPoint.objects.filter(
                pk=focused_id, conversation=conversation,
            ).select_related(
                "published_by", "represented_space", "visibility_audience",
                "response_audience", "resolution_audience",
            ).prefetch_related("options", "responses").first()
            if focused and focused.pk not in visible_timeline_ids and point_visible_to(request.user, focused):
                focused_point = _serialize_point(
                    focused, profile=request.user, section="focus",
                )
        label = conversation_context_label(conversation, request.user)
        from .core_models import ConversationParticipationStatus
        from .services import context_base_eligible
        membership = conversation.explicit_participations.filter(
            profile=request.user, status=ConversationParticipationStatus.ACTIVE,
        ).first()
        pending_request = conversation.join_requests.filter(
            requester=request.user, status="pending",
        ).first()
        self_eligible = context_base_eligible(request.user, conversation.context)
        state = conversation.user_states.filter(profile=request.user).first()
        return Response({
            "id": str(conversation.pk),
            "title": conversation.title_override or label,
            "purpose": conversation.purpose,
            "lifecycle": conversation.lifecycle,
            "entry_mode": conversation.entry_mode,
            "can_join": bool(
                self_eligible and not membership and conversation.entry_mode == "join"
                and conversation.lifecycle == "open"
            ),
            "can_request_entry": bool(
                self_eligible and not membership and not pending_request
                and conversation.entry_mode == "request"
                and conversation.lifecycle == "open"
            ),
            "entry_request_status": "pending" if pending_request else None,
            "my_participation": "active" if membership else None,
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
            "timeline": [
                _serialize_point(point, profile=request.user, section="timeline")
                for point in timeline["points"]
            ],
            "timeline_next_cursor": timeline["next_cursor"],
            "attention": conversation_attention_sections(
                request.user, conversation,
            ),
            "composer": composer_capabilities(request.user, conversation),
            "personal_state": {
                "muted": bool(state and state.muted_at),
                "hidden": bool(state and state.hidden_at),
                "archived": bool(state and state.archived_at),
                "pinned": bool(state and state.pinned_at),
                "revisit": bool(state and state.revisit_at),
            },
            "updated_at": conversation.updated_at,
            **conversation_detail_extra_for_profile(request.user, conversation, label),
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
                    multiple_choice=_request_boolean(request, "multiple_choice"),
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


class ConversationPointMediaResponseAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        uploaded = request.FILES.get("file")
        if uploaded is None:
            raise DRFValidationError({"file": "Choisissez un fichier."})
        declared = request.data.get("mime_type")
        if declared and uploaded.content_type in {"application/octet-stream", ""}:
            uploaded.content_type = str(declared)
        try:
            response, attachment = submit_point_media_response(
                actor=request.user, point=point,
                uploaded_file=uploaded, kind=request.data.get("kind", "file"),
                client_reference=request.data.get("client_reference"),
                represented_space=_represented_space_from_request(request),
            )
            return Response({
                "point_id": str(point.pk), "response_id": str(response.pk),
                "attachment": serialize_attachment(attachment),
            })
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)


class ConversationFormOptionsAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        return Response({
            "can_prepare": can_prepare_form(request.user, conversation),
            "results": available_form_versions(request.user, conversation),
        })


class ConversationFormComposeAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        try:
            point = publish_conversation_form(
                actor=request.user, conversation=conversation,
                title=request.data.get("title"),
                client_reference=request.data.get("client_reference"),
                form_version_id=request.data.get("form_version_id"),
                questions=request.data.get("questions"),
                audience_id=request.data.get("audience_id"),
                represented_space=_represented_space_from_request(request),
            )
            return Response({
                "id": str(point.pk), "point_id": str(point.pk), "kind": "form_request",
            })
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)


class ConversationSemanticMediaAPIView(PrivateNoStoreMixin, views.APIView):
    """Atomic upload of media associated to a Point and specific Poll choices."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        try:
            options = json.loads(request.data.get("options", "[]"))
            manifest = json.loads(request.data.get("media_manifest", "[]"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DRFValidationError({"media_manifest": "Structure invalide."}) from exc
        if not isinstance(options, list) or not all(isinstance(value, str) for value in options):
            raise DRFValidationError({"options": "Choix invalides."})
        if not isinstance(manifest, list) or not 1 <= len(manifest) <= 24:
            raise DRFValidationError({"media_manifest": "Prévoyez entre 1 et 24 médias."})
        if len(request.FILES) != len(manifest):
            raise DRFValidationError({"media_manifest": "Fichiers et légendes incohérents."})
        entries, file_fields = [], set()
        for index, raw in enumerate(manifest):
            if not isinstance(raw, dict):
                raise DRFValidationError({"media_manifest": "Entrée invalide."})
            field = raw.get("field")
            if field != f"media_{index}" or field in file_fields:
                raise DRFValidationError({"media_manifest": "Champ de fichier invalide."})
            file_fields.add(field)
            files = request.FILES.getlist(field)
            if len(files) != 1:
                raise DRFValidationError({field: "Un seul fichier attendu par emplacement."})
            uploaded = files[0]
            declared_mime = raw.get("mime_type")
            if (isinstance(declared_mime, str) and declared_mime
                    and uploaded.content_type in {"", "application/octet-stream"}):
                uploaded.content_type = declared_mime
            entries.append({
                "scope": raw.get("scope"),
                "option_index": raw.get("option_index"),
                "kind": raw.get("kind"),
                "caption": raw.get("caption", ""),
                "uploaded_file": uploaded,
            })
        try:
            point, attachments = publish_semantic_point_with_media(
                actor=request.user, conversation=conversation,
                kind=request.data.get("kind"),
                title=request.data.get("title", ""), body=request.data.get("body", ""),
                client_reference=request.data.get("client_reference"),
                options=options,
                multiple_choice=_request_boolean(request, "multiple_choice"),
                audience_id=request.data.get("audience_id") or None,
                represented_space=_represented_space_from_request(request),
                media_items=entries,
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)
        return Response({
            "kind": "point",
            "point_id": str(point.pk),
            "id": str(point.pk),
            "attachments": [serialize_attachment(item) for item in attachments],
        })


class ConversationMediaUploadAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        conversation = _visible_conversation_or_404(request.user, pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise DRFValidationError({"file": "Choisissez un fichier."})
        # The mobile multipart transport does not set per-file MIME. The
        # supplied declaration is only a candidate; owner validation checks
        # the actual file signature before any Point is created.
        declared = request.data.get("mime_type")
        if declared and upload.content_type in {"application/octet-stream", ""}:
            upload.content_type = str(declared)

        def structured_list(field):
            raw = request.data.get(field)
            if raw is None:
                return None
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError, json.JSONDecodeError):
                raise DRFValidationError({field: "Liste invalide."})
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise DRFValidationError({field: "Liste invalide."})
            return parsed

        options = structured_list("options")
        questions = structured_list("questions")
        try:
            point, attachment = upload_conversation_media(
                actor=request.user, conversation=conversation,
                uploaded_file=upload, kind=request.data.get("kind", "file"),
                body=request.data.get("body", ""),
                client_reference=request.data.get("client_reference"),
                point_id=request.data.get("point_id") or None,
                audience_id=request.data.get("audience_id") or None,
                represented_space=_represented_space_from_request(request),
                point_kind=request.data.get("point_kind") or None,
                title=request.data.get("title") or "",
                options=options,
                multiple_choice=request.data.get("multiple_choice", False),
                form_version_id=request.data.get("form_version_id") or None,
                questions=questions,
            )
            return Response({
                "point_id": str(point.pk), "attachment": serialize_attachment(attachment),
            })
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)


class ConversationAttachmentDownloadAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, attachment_pk):
        try:
            attachment = attachment_for_download(
                actor=request.user, attachment_id=attachment_pk,
            )
        except PermissionDenied as exc:
            raise NotFound("Pièce inaccessible.") from exc
        attachment.file.open("rb")
        reply = FileResponse(
            attachment.file, as_attachment=True, filename=attachment.original_name,
            content_type=attachment.mime_type,
        )
        reply["X-Content-Type-Options"] = "nosniff"
        reply["Cache-Control"] = "private, no-store"
        return reply


class ConversationExchangeEntriesAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        try:
            _, entry, target_id = contribute_text(
                actor=request.user, conversation=point.conversation,
                body=request.data.get("body"), point_id=str(point.pk),
                represented_space=_represented_space_from_request(request),
                client_reference=request.data.get("client_reference"),
            )
            return Response({"kind": "exchange", "id": str(entry.pk), "point_id": str(target_id)})
        except PermissionDenied:
            raise
        except ValidationError as exc:
            return _service_error(exc)

    def get(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        limit = _bounded_limit(request, default=25)
        try:
            entries, cursor = readable_exchange_entries(
                request.user, point, cursor=request.query_params.get("cursor"),
                limit=limit,
            )
        except PermissionDenied as exc:
            raise NotFound("Échange inaccessible.") from exc
        except ValidationError as exc:
            return _service_error(exc)
        return Response({
            "results": [
                {
                    "id": str(entry.pk), "body": entry.body,
                    "created_at": entry.created_at, "own": entry.author_id == request.user.pk,
                    "attachments": [
                        serialize_attachment(item)
                        for item in entry.attachments.all()
                        if can_download_attachment(request.user, item)
                    ],
                }
                for entry in entries
            ],
            "next_cursor": cursor,
        })


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


class ConversationPointCloseResponsesAPIView(PrivateNoStoreMixin, views.APIView):
    """Close responses only through the existing Conversation owner service."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        try:
            closed = close_point_responses(actor=request.user, point=point)
        except (PermissionDenied, ValidationError) as exc:
            return _service_error(exc)
        return Response({
            "point_id": str(closed.pk), "lifecycle": closed.lifecycle,
            "response_closed_at": closed.response_closed_at,
        })


class ConversationPointResolveAPIView(PrivateNoStoreMixin, views.APIView):
    """Coordination outcome, never a mutation of the contextual domain."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        summary = request.data.get("summary")
        options = request.data.get("selected_option_ids", [])
        if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > 500:
            raise DRFValidationError({"summary": "Un résultat de 1 à 500 caractères est attendu."})
        if not isinstance(options, list) or len(options) > 12 or any(
            not isinstance(value, str) or not value.strip() for value in options
        ) or len(set(options)) != len(options):
            raise DRFValidationError({"selected_option_ids": "Sélection de résultat invalide."})
        if options and point.kind != "poll":
            raise DRFValidationError({"selected_option_ids": "Seul un sondage permet de retenir des choix."})
        try:
            resolution = resolve_point(
                actor=request.user, point=point, summary=summary.strip(),
                selected_option_ids=options,
            )
        except (PermissionDenied, ValidationError) as exc:
            return _service_error(exc)
        return Response({
            "point_id": str(point.pk), "lifecycle": "resolved",
            "resolution_id": str(resolution.pk), "summary": resolution.summary,
            "resolved_at": resolution.resolved_at,
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


class ConversationPointPersonalStateAPIView(PrivateNoStoreMixin, views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, point_pk):
        point = _visible_point_or_404(request.user, point_pk)
        allowed = {"revisit", "pinned"}
        if not request.data or set(request.data) - allowed:
            raise DRFValidationError({"detail": "État personnel de Point inconnu."})
        changes = {}
        for key in allowed:
            if key in request.data:
                changes[key] = _request_boolean(request, key)
        try:
            state = update_point_personal_state(
                actor=request.user, point=point, **changes,
            )
        except (PermissionDenied, ValidationError) as exc:
            return _service_error(exc)
        return Response({
            "point_id": str(point.pk),
            "revisit": bool(state.revisit_at),
            "pinned": bool(state.pinned_at),
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
        from django.db.models import Q
        from .core_models import ConversationLifecycle
        now = timezone.now()
        limit = _bounded_limit(request)
        invitations = list(
            ConversationInvitation.objects.filter(
                invitee=request.user,
                status=ConversationInvitationStatus.PENDING,
                conversation__lifecycle=ConversationLifecycle.OPEN,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            ).select_related(
                "conversation", "conversation__context", "created_by"
            ).order_by("created_at", "id")[:limit + 1]
        )
        more_received = len(invitations) > limit
        invitations = invitations[:limit]
        collective = collective_invitation_inbox(request.user, limit=limit + 1)
        more_collective = len(collective) > limit
        return Response({
            "results": [
                {
                    "id": str(invitation.pk),
                    "conversation_id": str(invitation.conversation_id),
                    "invited_by": invitation.created_by.username,
                    "context_kind": invitation.conversation.context.kind,
                    "can_accept": invitation_accept_allowed(request.user, invitation),
                    "status": invitation.status,
                    "expires_at": invitation.expires_at,
                    "created_at": invitation.created_at,
                }
                for invitation in invitations
            ],
            "count": len(invitations),
            "more_received": more_received,
            "more_collective": more_collective,
            "collective_results": [
                {
                    "id": str(item.pk),
                    "conversation_id": str(item.conversation_id),
                    "invited_by": item.created_by.username,
                    "context_kind": item.conversation.context.kind,
                    "kind": "space" if item.space_id else "group",
                    "can_accept": collective_invitation_accept_allowed(request.user, item),
                    "identifier": item.space.slug if item.space_id else item.group.slug,
                    "label": item.space.name if item.space_id else item.group.name,
                    "status": item.status,
                    "expires_at": item.expires_at,
                    "created_at": item.created_at,
                }
                for item in collective[:limit]
            ],
            **participation_inbox_for_profile(request.user, limit=limit),
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

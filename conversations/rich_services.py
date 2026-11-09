"""C4 bridges from Conversation to canonical Questionnaires and private media.

All operations remain server-authorized; neither Form nor Attachment is a
shadow Conversation domain and none becomes a JourneyArtifact or Proof.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import can
from questionnaires.models import Form, FormStatus, FormVersion, FormVersionStatus, QuestionType
from questionnaires.services import (
    add_question, create_form, create_form_version, publish_form_version,
)

from .composing import (
    _active_exchange_points, _audience_for_publish, _clean_text,
    _validate_represented_context, composer_capabilities, contribute_text,
    publish_composed_point,
)
from .core_models import Conversation, ConversationLifecycle
from .form_services import _conversation_activity, ensure_form_requests_for_point
from .media_models import ConversationAttachmentKind, ConversationPointAttachment
from .media_services import (
    KIND_POLICY_FIELD, can_download_attachment, create_point_attachment,
    validate_conversation_upload,
)
from .point_models import (
    PointExchangeEntry, ConversationPoint, ConversationPointKind, ConversationPointLifecycle,
    ConversationPointResponse,
    ConversationPointResponseMode, ConversationResponseVisibility,
    ConversationExchangeModerationState,
)
from .point_services import create_point, point_visible_to, submit_point_response
from .services import can_manage_conversation, can_publish_in_conversation, can_view_conversation


def _form_context_activity(actor, conversation):
    if conversation.lifecycle != ConversationLifecycle.OPEN:
        return None
    policy = getattr(conversation, "policy", None)
    if policy is None or not policy.allow_form_requests:
        return None
    if not can_publish_in_conversation(actor, conversation):
        return None
    activity = _conversation_activity(conversation)
    if activity is None or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        return None
    return activity


def available_form_versions(actor, conversation):
    activity = _form_context_activity(actor, conversation)
    if activity is None:
        return []
    versions = FormVersion.objects.filter(
        form__activity=activity,
        form__status=FormStatus.ACTIVE,
        status=FormVersionStatus.PUBLISHED,
    ).select_related("form").order_by("form_id", "-version", "-published_at")[:200]
    seen = set()
    available = []
    for version in versions:
        if version.form_id in seen:
            continue
        seen.add(version.form_id)
        available.append({
            "id": str(version.pk), "title": version.title,
            "description": version.description[:240], "version": version.version,
        })
        if len(available) >= 50:
            break
    return available


def can_prepare_form(actor, conversation):
    return _form_context_activity(actor, conversation) is not None


def _validate_compose_reference(client_reference):
    if not isinstance(client_reference, str) or not 0 < len(client_reference.strip()) <= 80:
        raise ValidationError({"client_reference": "Référence de publication obligatoire."})
    return client_reference.strip()


@transaction.atomic
def publish_conversation_form(
    *, actor, conversation, title, client_reference, form_version_id=None,
    questions=None, audience_id=None, represented_space=None,
):
    # Serialize duplicate form preparations before the Form/Version rows are
    # created, not only when the canonical Point is published.
    conversation = Conversation.objects.select_for_update(of=("self",)).get(pk=conversation.pk)
    activity = _form_context_activity(actor, conversation)
    if activity is None:
        raise PermissionDenied("Vous ne pouvez pas demander de formulaire ici.")
    _validate_represented_context(conversation, represented_space)
    ref = _validate_compose_reference(client_reference)
    title = _clean_text(title, "title", limit=220)
    audience = _audience_for_publish(conversation, audience_id)
    if audience is None:
        raise ValidationError({"audience_id": "Choisissez les personnes concernées."})
    existing = ConversationPoint.objects.filter(client_reference=ref).first()
    if existing:
        if (existing.conversation_id != conversation.pk
                or existing.published_by_id != actor.pk
                or existing.kind != ConversationPointKind.FORM_REQUEST
                or existing.title != title
                or existing.visibility_audience_id != audience.pk
                or existing.represented_space_id != getattr(represented_space, "pk", None)):
            raise ValidationError("Cette référence d'idempotence est déjà utilisée.")
        link = existing.form_request_links.select_related("form_request").first()
        if link is None:
            raise ValidationError("Le formulaire précédent est incomplet.")
        if form_version_id and str(link.form_request.form_version_id) != str(form_version_id):
            raise ValidationError("Cette référence désigne un autre formulaire.")
        if questions is not None:
            actual = list(link.form_request.form_version.questions.order_by("position").values_list("label", flat=True))
            if actual != questions:
                raise ValidationError("La préparation du formulaire a changé.")
        return existing

    if form_version_id:
        try:
            version = FormVersion.objects.select_related("form").get(
                pk=form_version_id, form__activity=activity,
                form__status=FormStatus.ACTIVE, status=FormVersionStatus.PUBLISHED,
            )
        except (FormVersion.DoesNotExist, ValueError, TypeError, ValidationError) as exc:
            raise ValidationError({"form_version_id": "Formulaire indisponible."}) from exc
    else:
        if not isinstance(questions, list) or not 1 <= len(questions) <= 8:
            raise ValidationError({"questions": "Prévoyez entre une et huit questions."})
        labels = [_clean_text(label, "questions", limit=220) for label in questions]
        if len(set(labels)) != len(labels):
            raise ValidationError({"questions": "Chaque question doit être distincte."})
        # Only Questionnaire owns form structure; deterministic key protects a
        # retry under the same client reference without an orphan template.
        key = "conversation-" + sha256(f"{conversation.pk}:{ref}".encode()).hexdigest()[:28]
        form = create_form(activity=activity, key=key, title=title, actor=actor)
        version = create_form_version(form=form, actor=actor)
        for position, label in enumerate(labels):
            add_question(
                form_version=version, actor=actor, key=f"question_{position+1}",
                label=label, question_type=QuestionType.SHORT_TEXT,
                position=position, required=True,
            )
        publish_form_version(form_version=version, actor=actor)

    point = create_point(
        actor=actor, conversation=conversation,
        kind=ConversationPointKind.FORM_REQUEST,
        response_mode=ConversationPointResponseMode.NONE,
        title=title, visibility_audience=audience,
        expected_action_audience=audience,
        response_audience=audience,
        represented_space=represented_space,
        client_reference=ref,
    )
    ensure_form_requests_for_point(actor=actor, point=point, form_version=version)
    return point


def visible_attachments_for_profile(profile, point, *, limit=30):
    if not point_visible_to(profile, point):
        return []
    candidates = point.attachments.select_related(
        "response", "exchange_entry", "option", "point__conversation__context",
    ).order_by("created_at", "pk")[:max(1, min(limit, 100))]
    return [attachment for attachment in candidates if can_download_attachment(profile, attachment)]


def serialize_attachment(attachment):
    return {
        "id": str(attachment.pk),
        "kind": attachment.kind,
        "name": attachment.original_name,
        "caption": attachment.caption,
        "option_id": str(attachment.option_id) if attachment.option_id else None,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "download_path": f"api/v1/conversations/attachments/{attachment.pk}/download/",
    }


def readable_exchange_entries(profile, point, *, cursor=None, limit=25):
    if point.kind != ConversationPointKind.EXCHANGE or not point_visible_to(profile, point):
        raise PermissionDenied("Échange non accessible.")
    rows = point.exchange_entries.filter(
        moderation_state=ConversationExchangeModerationState.VISIBLE,
    )
    if not can_manage_conversation(profile, point.conversation):
        if point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS:
            pass
        elif point.response_visibility == ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES:
            rows = rows.filter(author=profile)
        else:
            rows = rows.none()
    if cursor:
        try:
            marker = rows.get(pk=UUID(str(cursor)))
        except (ValueError, TypeError, PointExchangeEntry.DoesNotExist) as exc:
            raise ValidationError({"cursor": "Curseur invalide."}) from exc
        rows = rows.filter(Q(created_at__gt=marker.created_at) | Q(
            created_at=marker.created_at, pk__gt=marker.pk,
        ))
    page = list(rows.order_by("created_at", "pk")[:limit+1])
    has_more = len(page) > limit
    page = page[:limit]
    return page, str(page[-1].pk) if has_more and page else None


@transaction.atomic
def upload_conversation_media(
    *, actor, conversation, uploaded_file, kind, client_reference,
    body="", audience_id=None, point_id=None, represented_space=None,
    point_kind=None, title="", options=None, multiple_choice=False,
    form_version_id=None, questions=None,
):
    """Upload a validated private attachment to an authorized Exchange or Point."""
    if kind not in ConversationAttachmentKind.values:
        raise ValidationError({"kind": "Type de pièce jointe inconnu."})
    ref = _validate_compose_reference(client_reference)
    if not can_view_conversation(actor, conversation):
        raise PermissionDenied("Conversation non accessible.")
    if conversation.lifecycle != ConversationLifecycle.OPEN:
        raise PermissionDenied("Conversation fermée.")
    _validate_represented_context(conversation, represented_space)
    policy = getattr(conversation, "policy", None)
    if policy is None or not getattr(policy, KIND_POLICY_FIELD[kind], False):
        raise PermissionDenied("Ce média n'est pas autorisé dans cette Conversation.")
    data, mime, digest = validate_conversation_upload(uploaded_file, kind)
    raw_name = Path(getattr(uploaded_file, "name", "fichier") or "fichier").name[:255]
    caption = (body or "").strip()
    if len(caption) > 5000:
        raise ValidationError({"body": "Ce texte est trop long."})
    # A typed contribution and its first attachment are one owner mutation.
    # Reuse Conversation Point, Questionnaire, and Attachment ownership:
    # do not create a second media-Point or a detached resource.
    if point_kind:
        if point_id:
            raise ValidationError({"point_id": "Choisissez un seul contexte d'envoi."})
        if point_kind == ConversationPointKind.FORM_REQUEST:
            point = publish_conversation_form(
                actor=actor, conversation=conversation, title=title,
                client_reference=ref, form_version_id=form_version_id,
                questions=questions, audience_id=audience_id,
                represented_space=represented_space,
            )
        elif point_kind in {
            ConversationPointKind.QUESTION, ConversationPointKind.REQUEST,
            ConversationPointKind.CONFIRMATION, ConversationPointKind.POLL,
        }:
            point = publish_composed_point(
                actor=actor, conversation=conversation, kind=point_kind,
                title=title, body=caption, options=options,
                multiple_choice=multiple_choice,
                audience_id=audience_id, represented_space=represented_space,
                client_reference=ref,
            )
        else:
            raise ValidationError({"point_kind": "Ce type de Point n'est pas autorisé."})
        entry = None
    else:
        active = _active_exchange_points(actor, conversation)
        if point_id:
            selected = next((point for point in active if str(point.pk) == str(point_id)), None)
            if selected is None:
                raise PermissionDenied("L'échange sélectionné est indisponible.")
        elif len(active) == 1:
            selected = active[0]
        elif len(active) > 1:
            raise ValidationError({"point_id": "Choisissez l'échange."})
        else:
            selected = None

        entry = None
        if selected is not None:
            _, entry, _ = contribute_text(
                actor=actor, conversation=conversation,
                body=caption or raw_name,
                point_id=str(selected.pk), represented_space=represented_space,
                client_reference=ref,
            )
            point = selected
        else:
            point = publish_composed_point(
                actor=actor, conversation=conversation,
                kind=ConversationPointKind.INFORMATION, body=caption or raw_name,
                audience_id=audience_id, represented_space=represented_space,
                client_reference=ref,
            )
    # A retry cannot add a second attachment or replace the bytes associated
    # with an already confirmed client reference.
    existing = point.attachments.filter(
        exchange_entry=entry, uploaded_by=actor,
    ).order_by("created_at", "pk").first()
    if existing is not None:
        if existing.kind != kind or existing.content_hash != digest:
            raise ValidationError("Cette référence d'envoi désigne un autre média.")
        return point, existing
    incoming = SimpleUploadedFile(raw_name, data, content_type=mime)
    attachment = create_point_attachment(
        actor=actor, point=point, uploaded_file=incoming, kind=kind,
        exchange_entry=entry,
    )
    return point, attachment


@transaction.atomic
def submit_point_media_response(
    *, actor, point, uploaded_file, kind, client_reference,
    represented_space=None,
):
    """A FILE/VOICE response is owned by ConversationPointResponse.

    The private attachment is associated with that response in the same DB
    transaction. Neither a free-text URL nor a new Information is created.
    """
    ref = _validate_compose_reference(client_reference)
    mode = point.response_mode
    if mode not in {ConversationPointResponseMode.FILE, ConversationPointResponseMode.VOICE}:
        raise ValidationError({"response_mode": "Ce Point n'attend pas de réponse média."})
    expected_kinds = {
        ConversationPointResponseMode.FILE: {ConversationAttachmentKind.FILE, ConversationAttachmentKind.IMAGE},
        ConversationPointResponseMode.VOICE: {ConversationAttachmentKind.VOICE, ConversationAttachmentKind.AUDIO},
    }
    if kind not in expected_kinds[mode]:
        raise ValidationError({"kind": "Type de média incompatible avec ce Point."})
    _validate_represented_context(point.conversation, represented_space)
    policy = getattr(point.conversation, "policy", None)
    if not policy or not getattr(policy, KIND_POLICY_FIELD[kind], False):
        raise PermissionDenied("Ce type de réponse n'est pas autorisé par la Conversation.")
    data, mime, digest = validate_conversation_upload(uploaded_file, kind)
    raw_name = Path(getattr(uploaded_file, "name", "fichier") or "fichier").name[:255]
    from .point_services import point_response_allowed
    if not point_response_allowed(actor, point):
        raise PermissionDenied("Réponse média non autorisée.")
    existing_response = ConversationPointResponse.objects.filter(
        client_reference=ref, point=point, actor=actor,
        represented_space=represented_space,
    ).first()
    if existing_response is not None:
        previous_attachment = existing_response.attachments.first()
        if previous_attachment is None or previous_attachment.kind != kind or previous_attachment.content_hash != digest:
            raise ValidationError("Cette référence de réponse désigne un autre fichier.")
        return existing_response, previous_attachment
    response = submit_point_response(
        actor=actor, point=point, value=None,
        represented_space=represented_space, client_reference=ref,
    )
    attachment = response.attachments.order_by("created_at", "pk").first()
    if attachment is not None:
        if attachment.kind != kind or attachment.content_hash != digest:
            raise ValidationError("Cette référence de réponse désigne un autre fichier.")
        return response, attachment
    attachment = create_point_attachment(
        actor=actor, point=point, uploaded_file=SimpleUploadedFile(
            raw_name, data, content_type=mime,
        ), kind=kind, response=response,
    )
    return response, attachment

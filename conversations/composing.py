"""C3 Conversations composition, delegating all writes to canonical Point services.

The returned capabilities are viewer-scoped hints. POST actions recheck the
same permissions, policy, audience, lifecycle and represented actor.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError

from authorization.constants import PermissionCode
from authorization.services import can
from django.utils import timezone

from .audience_models import ConversationAudienceSet, ConversationAudienceStatus
from .core_models import ConversationContext, ConversationContextKind, ConversationLifecycle
from .point_models import (
    ConversationPoint, ConversationPointKind, ConversationPointLifecycle,
    ConversationResponseVisibility,
    ConversationPointResolutionPolicy, ConversationPointResponseMode,
    PointExchangeEntry,
)
from .point_services import (
    POINT_POLICY_CAPABILITY, create_exchange_entry, create_point,
    point_response_allowed, point_visible_to,
)
from .services import _has_scope_permission, can_publish_in_conversation, can_view_conversation


COMPOSABLE_KINDS = {
    ConversationPointKind.INFORMATION,
    ConversationPointKind.QUESTION,
    ConversationPointKind.REQUEST,
    ConversationPointKind.CONFIRMATION,
    ConversationPointKind.POLL,
    ConversationPointKind.EXCHANGE,
}
MAX_TEXT_LENGTH = 5000


def _clean_text(value, field, *, limit=MAX_TEXT_LENGTH):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({field: "Ce champ est obligatoire."})
    value = value.strip()
    if len(value) > limit:
        raise ValidationError({field: "Ce texte est trop long."})
    return value


def _active_exchange_points(profile, conversation):
    policy = getattr(conversation, "policy", None)
    if conversation.lifecycle != ConversationLifecycle.OPEN or not policy or not policy.allow_free_exchange:
        return []
    now = timezone.now()
    candidates = ConversationPoint.objects.filter(
        conversation=conversation, kind=ConversationPointKind.EXCHANGE,
        lifecycle=ConversationPointLifecycle.OPEN,
    ).select_related("conversation", "visibility_audience", "response_audience").order_by("-published_at", "pk")[:50]
    return [
        point for point in candidates
        if (point.opens_at is None or point.opens_at <= now)
        and (point.deadline_at is None or point.deadline_at > now)
        and (point.valid_until is None or point.valid_until > now)
        and point_response_allowed(profile, point, at=now)
    ]


def composer_capabilities(profile, conversation):
    if not can_view_conversation(profile, conversation):
        raise PermissionDenied("Conversation non accessible.")
    policy = getattr(conversation, "policy", None)
    can_create = bool(
        conversation.lifecycle == ConversationLifecycle.OPEN
        and policy is not None and can_publish_in_conversation(profile, conversation)
    )
    allowed_kinds = sorted(
        kind for kind in COMPOSABLE_KINDS
        if can_create and getattr(policy, POINT_POLICY_CAPABILITY[kind], False)
    )
    audiences = list(ConversationAudienceSet.objects.filter(
        conversation=conversation, status=ConversationAudienceStatus.ACTIVE,
    ).order_by("label", "pk")) if can_create else []
    exchange_points = _active_exchange_points(profile, conversation)
    # A unique active Exchange accepts plain text; never guess among several.
    default_exchange_id = str(exchange_points[0].pk) if len(exchange_points) == 1 else None
    text_mode = (
        "exchange" if default_exchange_id else
        "exchange_select" if len(exchange_points) > 1 else
        "information" if ConversationPointKind.INFORMATION in allowed_kinds else
        None
    )
    representative_space = _context_space_for_composer(conversation)
    representable_space_id = (
        str(representative_space.pk)
        if representative_space is not None and
        can(profile, PermissionCode.SPACE_CONVERSATIONS_PUBLISH, space=representative_space)
        else None
    )
    from .media_services import KIND_POLICY_FIELD
    from .rich_services import available_form_versions, can_prepare_form
    can_send_media = bool(can_create or exchange_points)
    media_kinds = sorted(
        kind for kind, capability in KIND_POLICY_FIELD.items()
        if can_send_media and getattr(policy, capability, False)
    )
    form_options = available_form_versions(profile, conversation) if can_create else []
    return {
        "can_create": can_create,
        "can_form": bool(can_create and can_prepare_form(profile, conversation)),
        "form_options": form_options,
        "media_kinds": media_kinds,
        "allowed_kinds": allowed_kinds,
        "audiences": [{"id": str(item.pk), "label": item.label} for item in audiences],
        "audience_selection_required": len(audiences) > 1,
        "default_audience_id": str(audiences[0].pk) if len(audiences) == 1 else None,
        "text_mode": text_mode,
        "representable_space_id": representable_space_id,
        "default_exchange_point_id": default_exchange_id,
        "exchange_targets": [
            {"id": str(item.pk), "title": item.title or "Échange"}
            for item in exchange_points
        ],
    }


def _audience_for_publish(conversation, audience_id):
    if not audience_id:
        if conversation.audience_sets.filter(status=ConversationAudienceStatus.ACTIVE).count() > 1:
            raise ValidationError({"audience_id": "Choisissez les destinataires."})
        return conversation.audience_sets.filter(
            status=ConversationAudienceStatus.ACTIVE,
        ).first()
    try:
        return ConversationAudienceSet.objects.get(
            pk=audience_id, conversation=conversation,
            status=ConversationAudienceStatus.ACTIVE,
        )
    except (ConversationAudienceSet.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError({"audience_id": "Audience indisponible."}) from exc


def _context_space_for_composer(conversation):
    context = conversation.context
    if context.kind == ConversationContextKind.SPACE:
        return context.space
    if context.kind == ConversationContextKind.GROUP:
        return context.group.space
    if context.kind == ConversationContextKind.ACTIVITY:
        return context.activity.space
    if context.kind == ConversationContextKind.OCCURRENCE:
        return context.occurrence.activity.space
    if context.kind == ConversationContextKind.JOURNEY:
        return context.journey.activity.space
    if context.kind == ConversationContextKind.DOSSIER:
        return context.dossier.owning_space
    if context.kind == ConversationContextKind.PROJECT:
        return context.project.owning_space
    return None


def _validate_represented_context(conversation, represented_space):
    if represented_space is None:
        return
    owner_space = _context_space_for_composer(conversation)
    if owner_space is None or owner_space.pk != represented_space.pk:
        raise PermissionDenied("Cet Espace ne porte pas cette Conversation.")


def publish_composed_point(
    *, actor, conversation, kind, title="", body="", options=None,
    multiple_choice=False, audience_id=None, represented_space=None, client_reference=None,
):
    if kind not in COMPOSABLE_KINDS:
        raise ValidationError({"kind": "Ce type de Point n'est pas disponible."})
    if conversation.lifecycle != ConversationLifecycle.OPEN or not can_publish_in_conversation(actor, conversation):
        raise PermissionDenied("Publication non autorisée.")
    policy = getattr(conversation, "policy", None)
    if not policy or not getattr(policy, POINT_POLICY_CAPABILITY[kind], False):
        raise PermissionDenied("Ce type de Point n'est pas autorisé.")
    _validate_represented_context(conversation, represented_space)
    if not isinstance(client_reference, str) or not client_reference.strip() or len(client_reference) > 80:
        raise ValidationError({"client_reference": "Référence de publication obligatoire."})
    audience = _audience_for_publish(conversation, audience_id)
    title = (title or "").strip()
    body = (body or "").strip()
    if kind == ConversationPointKind.INFORMATION:
        body = _clean_text(body, "body")
        title = ""
    else:
        title = _clean_text(title, "title", limit=220)
        if len(body) > MAX_TEXT_LENGTH:
            raise ValidationError({"body": "Ce texte est trop long."})
    if not isinstance(multiple_choice, bool):
        raise ValidationError({"multiple_choice": "Valeur de choix multiples invalide."})
    if kind != ConversationPointKind.POLL and multiple_choice:
        raise ValidationError({"multiple_choice": "Cette option concerne uniquement les sondages."})
    if kind == ConversationPointKind.POLL:
        if not isinstance(options, list):
            raise ValidationError({"options": "Ajoutez au moins deux choix."})
        labels = [_clean_text(label, "options", limit=220) for label in options]
        if not 2 <= len(labels) <= 12 or len(set(labels)) != len(labels):
            raise ValidationError({"options": "Prévoyez entre 2 et 12 choix distincts."})
    else:
        if options:
            raise ValidationError({"options": "Aucun choix attendu pour ce Point."})
        labels = []
    mode = {
        ConversationPointKind.INFORMATION: ConversationPointResponseMode.NONE,
        ConversationPointKind.QUESTION: ConversationPointResponseMode.FREE_TEXT,
        # A Request is an action to take, not another open-ended question:
        # the expected recipient commits to taking it or declines explicitly.
        ConversationPointKind.REQUEST: ConversationPointResponseMode.BOOLEAN,
        ConversationPointKind.CONFIRMATION: ConversationPointResponseMode.BOOLEAN,
        ConversationPointKind.POLL: (
            ConversationPointResponseMode.MULTIPLE_CHOICE
            if multiple_choice else ConversationPointResponseMode.SINGLE_CHOICE
        ),
        ConversationPointKind.EXCHANGE: ConversationPointResponseMode.FREE_TEXT,
    }[kind]
    return create_point(
        actor=actor, conversation=conversation, kind=kind,
        response_mode=mode, title=title, body=body, options=labels,
        resolution_policy=(
            ConversationPointResolutionPolicy.PLURALITY
            if kind == ConversationPointKind.POLL
            else ConversationPointResolutionPolicy.MANUAL
        ),
        visibility_audience=audience,
        response_audience=audience if kind != ConversationPointKind.INFORMATION else None,
        expected_action_audience=(
            audience if kind == ConversationPointKind.REQUEST else None
        ),
        represented_space=represented_space,
        response_visibility=(
            ConversationResponseVisibility.POINT_VIEWERS
            if kind == ConversationPointKind.EXCHANGE
            else ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES
        ),
        client_reference=client_reference,
    )


def contribute_text(
    *, actor, conversation, body, point_id=None, represented_space=None,
    client_reference=None, audience_id=None,
):
    if not can_view_conversation(actor, conversation):
        raise PermissionDenied("Conversation non accessible.")
    _validate_represented_context(conversation, represented_space)
    body = _clean_text(body, "body")
    if not isinstance(client_reference, str) or not client_reference.strip() or len(client_reference) > 80:
        raise ValidationError({"client_reference": "Référence d'envoi obligatoire."})
    # The UI may have selected the only active Exchange implicitly, without
    # sending its point_id. A confirmed reference must still replay exactly
    # after that Exchange closes, never turn into a new Information Point.
    prior = PointExchangeEntry.objects.filter(
        client_reference=client_reference,
    ).select_related(
        "point__conversation__policy", "point__visibility_audience",
        "point__response_audience",
    ).first()
    if prior is not None:
        if (
            prior.point.conversation_id != conversation.pk
            or (point_id is not None and str(prior.point_id) != str(point_id))
        ):
            raise ValidationError("Cette référence d'idempotence est déjà utilisée.")
        entry = create_exchange_entry(
            actor=actor, point=prior.point, body=body,
            represented_space=represented_space,
            client_reference=client_reference,
        )
        return "exchange", entry, prior.point_id
    exchange_points = _active_exchange_points(actor, conversation)
    target = next((item for item in exchange_points if str(item.pk) == str(point_id)), None) if point_id else (
        exchange_points[0] if len(exchange_points) == 1 else None
    )
    if target is not None:
        entry = create_exchange_entry(
            actor=actor, point=target, body=body,
            represented_space=represented_space,
            client_reference=client_reference,
        )
        return "exchange", entry, target.pk
    if point_id:
        raise PermissionDenied("Cet échange n'est plus accessible.")
    if len(exchange_points) > 1:
        raise ValidationError({"point_id": "Choisissez l'échange auquel répondre."})
    if not can_publish_in_conversation(actor, conversation):
        raise PermissionDenied("Vous ne pouvez pas publier dans cette Conversation.")
    point = publish_composed_point(
        actor=actor, conversation=conversation,
        kind=ConversationPointKind.INFORMATION, body=body,
        represented_space=represented_space,
        audience_id=audience_id,
        client_reference=client_reference,
    )
    return "point", point, point.pk


def can_ensure_context_conversation(profile, kind, context_pk):
    """Only explicit manage authority permits contextual creation; never direct DM."""
    if kind not in ConversationContext.TARGET_FIELDS or kind == ConversationContextKind.DIRECT:
        return False
    field = ConversationContext.TARGET_FIELDS[kind][0]
    target_model = ConversationContext._meta.get_field(field).remote_field.model
    try:
        target = target_model.objects.get(pk=context_pk)
        pending = ConversationContext(kind=kind, **{field: target})
        pending.clean()
    except (target_model.DoesNotExist, ValidationError, ValueError, TypeError):
        return False
    return _has_scope_permission(profile, pending, "MANAGE")

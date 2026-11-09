from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .audience_services import conversation_viewer_ids, profile_in_audience, resolve_audience_ids
from .core_models import (
    Conversation, ConversationHistoryPolicy, ConversationLifecycle,
    ConversationParticipation, ConversationParticipationStatus,
)
from .point_models import (
    ConversationPoint,
    ConversationPointKind,
    ConversationPointLifecycle,
    ConversationPointOption,
    ConversationPointResolution,
    ConversationPointResolutionMethod,
    ConversationPointResolutionOption,
    ConversationPointResolutionPolicy,
    ConversationPointResponse,
    ConversationPointResponseMode,
    ConversationPointResponseStatus,
    ConversationPointUserState,
    PointExchangeEntry,
)
from .services import can_manage_conversation, can_publish_in_conversation, can_view_conversation


POINT_POLICY_CAPABILITY = {
    ConversationPointKind.INFORMATION: "allow_information",
    ConversationPointKind.QUESTION: "allow_questions",
    ConversationPointKind.CONFIRMATION: "allow_confirmations",
    ConversationPointKind.POLL: "allow_polls",
    ConversationPointKind.REQUEST: "allow_requests",
    ConversationPointKind.FORM_REQUEST: "allow_form_requests",
    ConversationPointKind.EXCHANGE: "allow_free_exchange",
}


def point_visible_to(
    profile, point, *, at=None,
    visibility_cache=None, audience_cache=None, history_cache=None,
):
    """Canonical viewer check with optional request-local memoization.

    Cache keys include the Profile and object identity. Callers never supply a
    positive authorization flag: the service fills every cache from the live
    policy itself. Recheck on every new request/acquisition.
    """
    scope = (getattr(profile, "pk", None), point.conversation_id)
    if visibility_cache is None:
        visible = can_view_conversation(profile, point.conversation)
    else:
        if scope not in visibility_cache:
            visibility_cache[scope] = can_view_conversation(profile, point.conversation)
        visible = visibility_cache[scope]
    if not visible:
        return False

    if point.lifecycle == ConversationPointLifecycle.DRAFT:
        if point.published_by_id != getattr(profile, "pk", None) and not can_manage_conversation(profile, point.conversation):
            return False
    if (
        point.published_at is not None
        and point.conversation.history_policy == ConversationHistoryPolicy.FROM_JOIN
    ):
        if history_cache is None:
            manager = can_manage_conversation(profile, point.conversation)
            from .participant_services import profile_conversation_since
            joined_at = None if manager else profile_conversation_since(
                profile, point.conversation,
            )
        else:
            if scope not in history_cache:
                manager = can_manage_conversation(profile, point.conversation)
                from .participant_services import profile_conversation_since
                joined_at = None if manager else profile_conversation_since(
                    profile, point.conversation,
                )
                history_cache[scope] = (manager, joined_at)
            manager, joined_at = history_cache[scope]
        # Only explicit or accepted collective admissions have a join time.
        if not manager and (joined_at is None or point.published_at < joined_at):
            return False

    if not point.visibility_audience_id:
        return True
    audience_scope = (getattr(profile, "pk", None), point.visibility_audience_id, at)
    if audience_cache is None:
        return profile_in_audience(profile, point.visibility_audience, at=at)
    if audience_scope not in audience_cache:
        audience_cache[audience_scope] = profile_in_audience(
            profile, point.visibility_audience, at=at,
        )
    return audience_cache[audience_scope]


def point_resolution_visible_to(profile, point, *, at=None):
    """Gate resolution summaries and all derived result projections.

    An ability to read the Point does not imply a right to its resolution.
    Contextual authorities may inspect the result; other viewers require an
    explicit resolution audience when one exists.
    """
    if not point_visible_to(profile, point, at=at):
        return False
    return (
        not point.resolution_audience_id
        or can_manage_conversation(profile, point.conversation)
        or profile_in_audience(profile, point.resolution_audience, at=at)
    )



def point_response_allowed(profile, point, *, at=None):
    if not point_visible_to(profile, point, at=at):
        return False
    # Publishing a Point does not remove its author's right to participate.
    # Everyone else remains constrained by the explicit response audience.
    if point.published_by_id == getattr(profile, "pk", None):
        return True
    return not point.response_audience_id or profile_in_audience(profile, point.response_audience, at=at)


def point_expected_from(profile, point, *, at=None):
    return bool(
        point_visible_to(profile, point, at=at)
        and point.expected_action_audience_id
        and profile_in_audience(profile, point.expected_action_audience, at=at)
    )


def _validate_represented_space(actor, represented_space):
    if represented_space and not can(actor, PermissionCode.SPACE_CONVERSATIONS_PUBLISH, space=represented_space):
        raise PermissionDenied("Vous n’êtes pas autorisé à agir au nom de cet Espace.")


def _active_window(point, *, at=None):
    at = at or timezone.now()
    if point.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("Cette Conversation est fermée.")
    if point.lifecycle != ConversationPointLifecycle.OPEN:
        raise ValidationError("Ce Point n’accepte pas de réponse actuellement.")
    if point.opens_at and at < point.opens_at:
        raise ValidationError("Ce Point n’est pas encore ouvert.")
    if point.deadline_at and at >= point.deadline_at:
        raise ValidationError("La période de réponse est terminée.")
    if point.valid_until and at >= point.valid_until:
        raise ValidationError("Ce Point n’est plus valide.")
    return at


def _choice_ids(point, value, *, multiple):
    raw = value if multiple else [value]
    if not isinstance(raw, list) or not raw:
        raise ValidationError({"value": "Une sélection est obligatoire."})
    normalized = [str(item) for item in raw]
    if len(set(normalized)) != len(normalized):
        raise ValidationError({"value": "Un choix ne peut pas être sélectionné plusieurs fois."})
    known = {str(value) for value in point.options.filter(pk__in=normalized).values_list("pk", flat=True)}
    if known != set(normalized):
        raise ValidationError({"value": "Un choix ne correspond pas aux options de ce Point."})
    ordered = [value for value in normalized if value in known]
    return ordered if multiple else ordered[0]


def validate_response_value(point, value):
    mode = point.response_mode
    if mode == ConversationPointResponseMode.NONE:
        raise ValidationError({"value": "Ce Point n’attend pas de réponse structurée."})
    if mode == ConversationPointResponseMode.FREE_TEXT:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError({"value": "Une réponse texte non vide est obligatoire."})
        return value.strip()
    if mode == ConversationPointResponseMode.BOOLEAN:
        if not isinstance(value, bool):
            raise ValidationError({"value": "Une réponse oui/non est obligatoire."})
        return value
    if mode == ConversationPointResponseMode.SINGLE_CHOICE:
        return _choice_ids(point, value, multiple=False)
    if mode == ConversationPointResponseMode.MULTIPLE_CHOICE:
        return _choice_ids(point, value, multiple=True)
    if mode == ConversationPointResponseMode.NUMBER:
        try:
            return str(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({"value": "Une valeur numérique valide est obligatoire."}) from exc
    if mode == ConversationPointResponseMode.DATE:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value.isoformat()
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise ValidationError({"value": "Une date ISO valide est obligatoire."}) from exc
    if mode == ConversationPointResponseMode.DATETIME:
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value))
            except ValueError as exc:
                raise ValidationError({"value": "Une date/heure ISO valide est obligatoire."}) from exc
        if timezone.is_naive(parsed):
            raise ValidationError({"value": "La date/heure doit inclure son fuseau horaire."})
        return parsed.isoformat()
    if mode in {ConversationPointResponseMode.FILE, ConversationPointResponseMode.VOICE}:
        if value not in (None, ""):
            raise ValidationError({"value": "Le fichier ou vocal est transmis par le bridge média J6, jamais comme URL libre."})
        return None
    raise ValidationError({"value": "Mode de réponse non pris en charge."})


def _assert_policy_allows(point):
    policy = getattr(point.conversation, "policy", None)
    if policy is None:
        raise ValidationError("La Conversation doit avoir une policy avant de publier un Point.")
    if not getattr(policy, POINT_POLICY_CAPABILITY[point.kind]):
        raise ValidationError({"kind": "Ce type de Point n’est pas autorisé par la policy de la Conversation."})


@transaction.atomic
def create_point(
    *, actor, conversation, kind, response_mode=ConversationPointResponseMode.NONE,
    resolution_policy=ConversationPointResolutionPolicy.MANUAL, title="", body="", importance="normal",
    visibility_audience=None, response_audience=None, expected_action_audience=None, resolution_audience=None,
    response_visibility="respondent_and_authorities", requires_acknowledgement=False,
    opens_at=None, deadline_at=None, valid_until=None, allow_response_change=False, threshold_value=None,
    represented_space=None, client_reference=None, options=(), publish=True,
):
    # Serialize creation for one Conversation so retries with the same client
    # reference do not race on the global uniqueness constraint.
    conversation = Conversation.objects.select_for_update(of=("self",)).get(pk=conversation.pk)
    if not can_publish_in_conversation(actor, conversation):
        raise PermissionDenied("Vous ne pouvez pas publier dans cette Conversation.")
    if conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation doit être ouverte pour publier un Point.")
    _validate_represented_space(actor, represented_space)
    ref = (client_reference or "").strip() or None
    if ref:
        existing = ConversationPoint.objects.filter(client_reference=ref).first()
        if existing:
            same_request = (
                existing.conversation_id == conversation.pk
                and existing.published_by_id == actor.pk
                and existing.kind == kind
                and existing.response_mode == response_mode
                and existing.title == (title or "").strip()
                and existing.body == (body or "").strip()
                and existing.visibility_audience_id == getattr(visibility_audience, "pk", None)
                and existing.response_audience_id == getattr(response_audience, "pk", None)
                and existing.expected_action_audience_id == getattr(expected_action_audience, "pk", None)
                and existing.represented_space_id == getattr(represented_space, "pk", None)
                and list(existing.options.order_by("position").values_list("label", flat=True)) == list(options)
            )
            if same_request:
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    point = ConversationPoint(
        conversation=conversation, kind=kind, response_mode=response_mode, resolution_policy=resolution_policy,
        title=title, body=body, importance=importance, visibility_audience=visibility_audience,
        response_audience=response_audience, expected_action_audience=expected_action_audience,
        resolution_audience=resolution_audience, response_visibility=response_visibility,
        requires_acknowledgement=requires_acknowledgement, opens_at=opens_at, deadline_at=deadline_at,
        valid_until=valid_until, allow_response_change=allow_response_change, threshold_value=threshold_value,
        represented_space=represented_space, client_reference=ref, published_by=actor,
    )
    point.save()
    for position, label in enumerate(options):
        ConversationPointOption.objects.create(point=point, label=label, position=position)
    return publish_point(actor=actor, point=point) if publish else point


@transaction.atomic
def publish_point(*, actor, point):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation__policy").get(pk=point.pk)
    if not can_publish_in_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas publier ce Point.")
    if locked.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation est fermée.")
    if locked.lifecycle != ConversationPointLifecycle.DRAFT:
        return locked
    _assert_policy_allows(locked)
    if locked.response_mode in {ConversationPointResponseMode.SINGLE_CHOICE, ConversationPointResponseMode.MULTIPLE_CHOICE} and locked.options.count() < 2:
        raise ValidationError("Un Point à choix exige au moins deux options.")
    now = timezone.now()
    locked.lifecycle = ConversationPointLifecycle.OPEN
    locked.published_at = now
    locked.opens_at = locked.opens_at or now
    locked._allow_lifecycle_transition = True
    locked.save(update_fields=["lifecycle", "published_at", "opens_at", "updated_at"])
    return locked


@transaction.atomic
def submit_point_response(*, actor, point, value=None, represented_space=None, client_reference=None):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related(
        "conversation", "visibility_audience", "response_audience", "expected_action_audience"
    ).get(pk=point.pk)
    at = timezone.now()
    if not point_response_allowed(actor, locked, at=at):
        raise PermissionDenied("Vous ne pouvez pas répondre à ce Point.")
    _validate_represented_space(actor, represented_space)
    normalized = validate_response_value(locked, value)
    ref = (client_reference or "").strip() or None
    if ref:
        existing = ConversationPointResponse.objects.filter(client_reference=ref).first()
        if existing:
            same_subject = existing.actor_id == actor.pk and existing.represented_space_id == getattr(represented_space, "pk", None)
            if existing.point_id == locked.pk and same_subject and existing.value == normalized:
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    # A confirmed response replay is valid even if the Point closed meanwhile.
    # A new response must still pass the current owner lifecycle gate.
    at = _active_window(locked, at=at)
    filters = {"represented_space": represented_space} if represented_space else {"actor": actor, "represented_space__isnull": True}
    previous = ConversationPointResponse.objects.select_for_update().filter(point=locked, status=ConversationPointResponseStatus.ACTIVE, **filters).first()
    if previous and not locked.allow_response_change:
        raise ValidationError("Une réponse active existe déjà et ce Point n’autorise pas sa modification.")
    if previous:
        previous.status = ConversationPointResponseStatus.SUPERSEDED
        previous.save(update_fields=["status", "updated_at"])
    try:
        response = ConversationPointResponse.objects.create(
            point=locked, actor=actor, represented_space=represented_space, value=normalized,
            supersedes=previous, client_reference=ref, submitted_at=at,
        )
    except IntegrityError as exc:
        raise ValidationError("Une réponse active existe déjà pour ce sujet.") from exc
    maybe_auto_resolve(point=locked, allow_open=True)
    return response


@transaction.atomic
@transaction.atomic
def update_point_personal_state(*, actor, point, revisit=None, pinned=None):
    """Viewer-owned state only; does not close, resolve or reorder the Point."""
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related(
        "conversation", "conversation__context", "visibility_audience",
    ).get(pk=point.pk)
    if not point_visible_to(actor, locked):
        raise PermissionDenied("Ce Point n'est plus accessible.")
    if revisit is None and pinned is None:
        raise ValidationError("Aucun changement personnel demandé.")
    state, _ = ConversationPointUserState.objects.select_for_update().get_or_create(
        point=locked, profile=actor,
    )
    now = timezone.now()
    if revisit is not None:
        if not isinstance(revisit, bool):
            raise ValidationError({"revisit": "Valeur booléenne attendue."})
        state.revisit_at = now if revisit else None
    if pinned is not None:
        if not isinstance(pinned, bool):
            raise ValidationError({"pinned": "Valeur booléenne attendue."})
        state.pinned_at = now if pinned else None
    state.save(update_fields=["revisit_at", "pinned_at", "updated_at"])
    return state


def acknowledge_point(*, actor, point):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation", "visibility_audience").get(pk=point.pk)
    if locked.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation est fermée.")
    if not locked.requires_acknowledgement:
        raise ValidationError("Ce Point ne demande pas de confirmation de lecture.")
    if not point_visible_to(actor, locked):
        raise PermissionDenied("Ce Point n’est pas accessible.")
    if locked.expected_action_audience_id and not point_expected_from(actor, locked):
        raise PermissionDenied("Cette confirmation de lecture ne vous est pas destinée.")
    if locked.lifecycle not in {
        ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED,
    }:
        raise ValidationError("Ce Point n'attend plus de confirmation de lecture.")
    now = timezone.now()
    if locked.opens_at and locked.opens_at > now:
        raise ValidationError("La prise de connaissance n'est pas encore ouverte.")
    if locked.valid_until and locked.valid_until <= now:
        raise ValidationError("Ce Point n'est plus valide.")
    state, _ = ConversationPointUserState.objects.select_for_update().get_or_create(point=locked, profile=actor)
    now = timezone.now()
    state.seen_at = state.seen_at or now
    state.acknowledged_at = state.acknowledged_at or now
    state.save(update_fields=["seen_at", "acknowledged_at", "updated_at"])
    return state


def _option_counts(point):
    counts = {str(option.pk): 0 for option in point.options.all()}
    for response in point.responses.filter(status=ConversationPointResponseStatus.ACTIVE):
        selected = [response.value] if point.response_mode == ConversationPointResponseMode.SINGLE_CHOICE else response.value if isinstance(response.value, list) else []
        for option_id in selected:
            if str(option_id) in counts:
                counts[str(option_id)] += 1
    return counts


def _eligible_subject_count(point):
    audience = point.expected_action_audience or point.response_audience
    return len(resolve_audience_ids(audience)) if audience else len(conversation_viewer_ids(point.conversation))


def _automatic_selection(point, *, allow_open):
    policy = point.resolution_policy
    responses = point.responses.filter(status=ConversationPointResponseStatus.ACTIVE).order_by("submitted_at", "id")
    if policy == ConversationPointResolutionPolicy.FIRST_VALID:
        first = responses.first()
        return ([], {"response_id": str(first.pk)}) if first else None
    if policy in {ConversationPointResolutionPolicy.MANUAL, ConversationPointResolutionPolicy.NO_OUTCOME}:
        return None
    if point.response_mode not in {ConversationPointResponseMode.SINGLE_CHOICE, ConversationPointResponseMode.MULTIPLE_CHOICE}:
        return None
    counts = _option_counts(point)
    max_count = max(counts.values(), default=0)
    winners = [option_id for option_id, count in counts.items() if count == max_count and count > 0]
    if len(winners) != 1:
        return None
    winner = winners[0]
    if allow_open and policy != ConversationPointResolutionPolicy.THRESHOLD:
        return None
    eligible = _eligible_subject_count(point)
    if policy == ConversationPointResolutionPolicy.PLURALITY:
        return [winner], {"counts": counts}
    if policy == ConversationPointResolutionPolicy.ABSOLUTE_MAJORITY:
        return ([winner], {"counts": counts, "eligible": eligible}) if eligible and max_count > eligible / 2 else None
    if policy == ConversationPointResolutionPolicy.UNANIMITY:
        return ([winner], {"counts": counts, "eligible": eligible}) if eligible and max_count == eligible else None
    if policy == ConversationPointResolutionPolicy.THRESHOLD:
        return ([winner], {"counts": counts, "threshold": point.threshold_value}) if max_count >= point.threshold_value else None
    return None


def _create_resolution(*, point, method, summary, resolved_by, result_payload, selected_option_ids):
    now = timezone.now()
    resolution = ConversationPointResolution.objects.create(
        point=point, method=method, summary=summary, resolved_by=resolved_by, resolved_at=now,
        result_payload=result_payload or {},
    )
    requested = {str(value) for value in selected_option_ids}
    if requested:
        options = list(point.options.filter(pk__in=requested))
        if {str(option.pk) for option in options} != requested:
            raise ValidationError("Une option de résolution n’appartient pas à ce Point.")
        for option in options:
            ConversationPointResolutionOption.objects.create(resolution=resolution, option=option)
    point.lifecycle = ConversationPointLifecycle.RESOLVED
    point.resolved_at = now
    point.response_closed_at = point.response_closed_at or now
    point._allow_lifecycle_transition = True
    point.save(update_fields=["lifecycle", "resolved_at", "response_closed_at", "updated_at"])
    return resolution


@transaction.atomic
def maybe_auto_resolve(*, point, allow_open=False):
    locked = ConversationPoint.objects.select_for_update().get(pk=point.pk)
    allowed_states = {ConversationPointLifecycle.RESPONSE_CLOSED}
    if allow_open:
        allowed_states.add(ConversationPointLifecycle.OPEN)
    if locked.lifecycle not in allowed_states:
        return None
    selection = _automatic_selection(locked, allow_open=locked.lifecycle == ConversationPointLifecycle.OPEN)
    if not selection:
        return None
    option_ids, payload = selection
    return _create_resolution(
        point=locked, method=ConversationPointResolutionMethod.AUTOMATIC,
        summary=(
            "Choix retenu : " + (locked.options.filter(pk=option_ids[0]).values_list("label", flat=True).first() or "Résultat")
            if option_ids else "Résultat déterminé selon la règle configurée."
        ), resolved_by=None,
        result_payload=payload, selected_option_ids=option_ids,
    )


@transaction.atomic
def resolve_point(*, actor, point, summary, selected_option_ids=(), result_payload=None, method=ConversationPointResolutionMethod.MANUAL):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation", "resolution_audience").get(pk=point.pk)
    if not can_manage_conversation(actor, locked.conversation):
        raise PermissionDenied("La résolution exige l'autorité de gestion de la Conversation.")
    if locked.resolution_audience_id and not profile_in_audience(actor, locked.resolution_audience):
        raise PermissionDenied("Vous ne faites pas partie de l'audience de résolution.")
    if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > 500:
        raise ValidationError({"summary": "Résumez le résultat en 1 à 500 caractères."})
    if locked.lifecycle == ConversationPointLifecycle.RESOLVED:
        existing = locked.resolution
        current_options = {
            str(option_id) for option_id in existing.selected_option_links.values_list(
                "option_id", flat=True,
            )
        }
        requested_options = {str(option_id) for option_id in selected_option_ids}
        if existing.summary != summary.strip() or current_options != requested_options:
            raise ValidationError(
                "Ce Point est déjà résolu avec un autre résultat. Actualisez son état."
            )
        return existing
    if not isinstance(selected_option_ids, (list, tuple)) or len(selected_option_ids) > 12:
        raise ValidationError({"selected_option_ids": "Choix retenus invalides."})
    if selected_option_ids and locked.kind != ConversationPointKind.POLL:
        raise ValidationError({"selected_option_ids": "Seul un sondage permet de retenir des choix."})
    if locked.lifecycle not in {ConversationPointLifecycle.OPEN, ConversationPointLifecycle.RESPONSE_CLOSED}:
        raise ValidationError("Ce Point ne peut pas être résolu dans son état actuel.")
    if locked.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation est fermée.")
    return _create_resolution(
        point=locked, method=method, summary=summary, resolved_by=actor,
        result_payload=result_payload or {}, selected_option_ids=selected_option_ids,
    )


@transaction.atomic
def close_point_responses(*, actor, point):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation").get(pk=point.pk)
    if locked.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation est fermée.")
    if not can_manage_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas fermer les réponses de ce Point.")
    if locked.response_mode == ConversationPointResponseMode.NONE or locked.kind == ConversationPointKind.FORM_REQUEST:
        raise ValidationError("Ce Point n'a pas de réponses Conversation à clore.")
    if locked.lifecycle != ConversationPointLifecycle.OPEN:
        return locked
    locked.lifecycle = ConversationPointLifecycle.RESPONSE_CLOSED
    locked.response_closed_at = timezone.now()
    locked._allow_lifecycle_transition = True
    locked.save(update_fields=["lifecycle", "response_closed_at", "updated_at"])
    maybe_auto_resolve(point=locked)
    return ConversationPoint.objects.get(pk=locked.pk)


@transaction.atomic
def supersede_point(*, actor, old_point, new_point):
    old = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation").get(pk=old_point.pk)
    if old.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("La Conversation est fermée.")
    if old.conversation_id != new_point.conversation_id:
        raise ValidationError("Le Point de remplacement doit appartenir à la même Conversation.")
    if not can_publish_in_conversation(actor, old.conversation):
        raise PermissionDenied("Vous ne pouvez pas remplacer ce Point.")
    if new_point.lifecycle == ConversationPointLifecycle.DRAFT:
        new_point.supersedes = old
        new_point.save(update_fields=["supersedes", "updated_at"])
        publish_point(actor=actor, point=new_point)
    elif new_point.supersedes_id != old.pk:
        raise ValidationError("Le nouveau Point publié doit référencer le Point remplacé.")
    old.lifecycle = ConversationPointLifecycle.SUPERSEDED
    old._allow_lifecycle_transition = True
    old.save(update_fields=["lifecycle", "updated_at"])
    return new_point


@transaction.atomic
def create_exchange_entry(*, actor, point, body, reply_to=None, represented_space=None, client_reference=None):
    locked = ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation__policy", "visibility_audience", "response_audience").get(pk=point.pk)
    _active_window(locked)
    if locked.kind != ConversationPointKind.EXCHANGE or not locked.conversation.policy.allow_free_exchange:
        raise ValidationError("Ce Point n’autorise pas la discussion libre.")
    if not point_response_allowed(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas contribuer à cet échange.")
    _validate_represented_space(actor, represented_space)
    ref = (client_reference or "").strip() or None
    if ref:
        existing = PointExchangeEntry.objects.filter(client_reference=ref).first()
        if existing:
            if (
                existing.point_id == locked.pk and existing.author_id == actor.pk
                and existing.body == (body or "").strip()
                and existing.represented_space_id == getattr(represented_space, "pk", None)
                and existing.reply_to_id == getattr(reply_to, "pk", None)
            ):
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    return PointExchangeEntry.objects.create(
        point=locked, author=actor, represented_space=represented_space, body=body,
        reply_to=reply_to, client_reference=ref,
    )

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from social.models import ActionProposalDirection, ActionProposalStatus

from .involvement_models import (
    ActivityInvolvement,
    ActivityInvolvementConfirmationBasis,
    ActivityInvolvementExternalKind,
    ActivityInvolvementFunction,
    ActivityInvolvementFunctionKind,
    ActivityInvolvementNeedConfig,
    ActivityInvolvementStatus,
    ActivityInvolvementVisibility,
)


def _emit_involvement_event(*, involvement, event_type, suffix):
    payload = {
        "activity_id": str(involvement.activity_id),
        "occurrence_id": str(involvement.occurrence_id) if involvement.occurrence_id else None,
        "profile_id": str(involvement.profile_id) if involvement.profile_id else None,
        "space_id": str(involvement.space_id) if involvement.space_id else None,
        "confirmation_basis": involvement.confirmation_basis,
        "visibility": involvement.visibility,
        "status": involvement.status,
    }
    emit_domain_event(
        event_type=event_type,
        source_type="activity_involvement",
        source_id=involvement.pk,
        idempotency_key=f"activity-involvement:{involvement.pk}:{suffix}",
        payload=payload,
    )


def _can_manage_involvement(actor, activity) -> bool:
    return can(actor, PermissionCode.ACTIVITY_ACTION_NETWORK_MANAGE, activity=activity)


@transaction.atomic
def realize_activity_proposal(*, actor, proposal):
    """Idempotently materialize the Activity truth owned by a configured Need."""

    if proposal.status != ActionProposalStatus.ACCEPTED:
        raise ValidationError("Seule une proposition acceptée peut être matérialisée.")
    try:
        config = ActivityInvolvementNeedConfig.objects.select_related(
            "need", "need__activity", "need__occurrence"
        ).get(need_id=proposal.need_id)
    except ActivityInvolvementNeedConfig.DoesNotExist:
        return None

    existing = ActivityInvolvement.objects.filter(source_proposal_id=proposal.pk).first()
    if existing:
        return existing

    need = config.need
    if proposal.candidate_profile_id:
        confirmation_basis = ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED
        profile_id = proposal.candidate_profile_id
        space_id = None
    elif proposal.candidate_space_id:
        confirmation_basis = ActivityInvolvementConfirmationBasis.SPACE_CONFIRMED
        profile_id = None
        space_id = proposal.candidate_space_id
    else:
        raise ValidationError("La proposition acceptée n'a pas de candidat canonique.")

    if proposal.direction == ActionProposalDirection.CANDIDATE_TO_OWNER:
        confirmed_by_id = proposal.initiated_by_id
    else:
        confirmed_by_id = proposal.responded_by_id or getattr(actor, "pk", None)

    involvement = ActivityInvolvement.objects.create(
        activity_id=need.activity_id,
        occurrence_id=need.occurrence_id,
        profile_id=profile_id,
        space_id=space_id,
        contextual_title=config.function_label,
        visibility=config.result_visibility,
        confirmation_basis=confirmation_basis,
        source_proposal=proposal,
        recorded_by_id=need.created_by_id,
        confirmed_by_id=confirmed_by_id,
        confirmed_at=proposal.responded_at or timezone.now(),
    )
    ActivityInvolvementFunction.objects.create(
        involvement=involvement,
        kind=config.function_kind,
        label=config.function_label,
        presentation_tier=config.presentation_tier,
        presentation_order=config.presentation_order,
    )
    _emit_involvement_event(
        involvement=involvement,
        event_type=DomainEventType.ACTIVITY_INVOLVEMENT_CREATED,
        suffix="created",
    )
    return involvement


@transaction.atomic
def create_external_involvement(
    *, actor, activity, external_display_name, external_kind=ActivityInvolvementExternalKind.PERSON,
    occurrence=None, contextual_title="", short_description="",
    visibility=ActivityInvolvementVisibility.CONTEXT,
    function_kind=ActivityInvolvementFunctionKind.OTHER,
    function_label="", presentation_tier=3, presentation_order=0,
):
    if not _can_manage_involvement(actor, activity):
        raise PermissionDenied("Cette Activity exige l'autorité de gestion du réseau d'action.")
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L'Occurrence doit appartenir à l'Activity."})
    involvement = ActivityInvolvement.objects.create(
        activity=activity,
        occurrence=occurrence,
        external_kind=external_kind,
        external_display_name=external_display_name,
        contextual_title=contextual_title,
        short_description=short_description,
        visibility=visibility,
        confirmation_basis=ActivityInvolvementConfirmationBasis.ORGANIZER_DECLARED,
        recorded_by=actor,
    )
    ActivityInvolvementFunction.objects.create(
        involvement=involvement,
        kind=function_kind,
        label=function_label,
        presentation_tier=presentation_tier,
        presentation_order=presentation_order,
    )
    _emit_involvement_event(
        involvement=involvement,
        event_type=DomainEventType.ACTIVITY_INVOLVEMENT_CREATED,
        suffix="created",
    )
    return involvement


@transaction.atomic
def create_direct_confirmed_involvement(
    *, actor, activity, profile=None, space=None, occurrence=None,
    contextual_title="", short_description="",
    visibility=ActivityInvolvementVisibility.CONTEXT,
    function_kind=ActivityInvolvementFunctionKind.OTHER,
    function_label="", presentation_tier=3, presentation_order=0,
):
    """Safe direct path only when the acting subject can confirm itself."""

    if not _can_manage_involvement(actor, activity):
        raise PermissionDenied("Cette Activity exige l'autorité de gestion du réseau d'action.")
    if bool(profile) == bool(space):
        raise ValidationError("Choisissez exactement un Profile ou un Space.")
    if profile is not None:
        if profile.pk != getattr(actor, "pk", None):
            raise PermissionDenied("Un autre Profile doit confirmer via une ActionProposal.")
        basis = ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED
    else:
        if not can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=space):
            raise PermissionDenied("Le représentant doit être autorisé à agir pour le réseau d'action de ce Space.")
        basis = ActivityInvolvementConfirmationBasis.SPACE_CONFIRMED
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L'Occurrence doit appartenir à l'Activity."})
    involvement = ActivityInvolvement.objects.create(
        activity=activity,
        occurrence=occurrence,
        profile=profile,
        space=space,
        contextual_title=contextual_title,
        short_description=short_description,
        visibility=visibility,
        confirmation_basis=basis,
        recorded_by=actor,
        confirmed_by=actor,
        confirmed_at=timezone.now(),
    )
    ActivityInvolvementFunction.objects.create(
        involvement=involvement,
        kind=function_kind,
        label=function_label,
        presentation_tier=presentation_tier,
        presentation_order=presentation_order,
    )
    _emit_involvement_event(
        involvement=involvement,
        event_type=DomainEventType.ACTIVITY_INVOLVEMENT_CREATED,
        suffix="created",
    )
    return involvement


@transaction.atomic
def remove_activity_involvement(*, actor, involvement: ActivityInvolvement):
    locked = ActivityInvolvement.objects.select_for_update().select_related("activity", "activity__space").get(pk=involvement.pk)
    if not _can_manage_involvement(actor, locked.activity):
        raise PermissionDenied("Vous ne pouvez pas retirer cette implication.")
    if locked.status == ActivityInvolvementStatus.REMOVED:
        return locked
    locked.status = ActivityInvolvementStatus.REMOVED
    locked.removed_by = actor
    locked.removed_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "removed_by", "removed_at", "updated_at"])
    _emit_involvement_event(
        involvement=locked,
        event_type=DomainEventType.ACTIVITY_INVOLVEMENT_REMOVED,
        suffix="removed",
    )
    return locked
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from authorization.permissions import PermissionCode
from authorization.services import can
from core.domain_events import DomainEventType, emit_domain_event
from organizations.models import MembershipStatus, Organization
from topics.models import ActionMatchKind, ProfileOpenTo, SpaceOpenTo

from .models import (
    ActionBlock,
    ActionBlockReason,
    ActionNeed,
    ActionNeedCandidateKind,
    ActionNeedIntakePolicy,
    ActionNeedStatus,
    ActionNeedVisibility,
    ActionProposal,
    ActionProposalDirection,
    ActionProposalStatus,
)


ACTIVE_NEED_STATUSES = {ActionNeedStatus.OPEN, ActionNeedStatus.PAUSED}
ACTIONABLE_NEED_STATUSES = {ActionNeedStatus.OPEN}
ACTIVE_PROPOSAL_STATUSES = {ActionProposalStatus.PENDING, ActionProposalStatus.ACCEPTED}


def can_manage_action_need(actor, need: ActionNeed) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    if need.owner_profile_id:
        return need.owner_profile_id == actor.pk
    if need.space_id:
        return can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=need.space)
    return False


def _require_need_owner(actor, *, owner_profile=None, space=None) -> None:
    if bool(owner_profile) == bool(space):
        raise ValidationError("Un besoin appartient soit à un Profile, soit à un Space.")
    if owner_profile is not None:
        if owner_profile.pk != actor.pk:
            raise PermissionDenied("Vous ne pouvez publier un besoin personnel que pour votre propre Profile.")
        return
    if not can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=space):
        raise PermissionDenied("Ce besoin Space exige l'autorité de gestion du réseau d'action.")


def _require_candidate_authority(*, actor, candidate_profile=None, candidate_space=None) -> None:
    if bool(candidate_profile) == bool(candidate_space):
        raise ValidationError("Une proposition candidate doit venir soit d'un Profile, soit d'un Space.")
    if candidate_profile is not None:
        if candidate_profile.pk != actor.pk:
            raise PermissionDenied("Vous ne pouvez proposer que votre propre Profile.")
        return
    if not can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=candidate_space):
        raise PermissionDenied("Cette proposition Space exige l'autorité de gestion du réseau d'action.")


def _normalize_kind(match_kind: str) -> str:
    if match_kind not in ActionMatchKind.values:
        raise ValidationError({"match_kind": "Type de besoin d'action inconnu."})
    return match_kind


def _need_accepts_new_proposals(need: ActionNeed, *, at=None) -> None:
    at = at or timezone.now()
    if need.status not in ACTIONABLE_NEED_STATUSES:
        raise ValidationError("Ce besoin n'accepte pas de nouvelles propositions dans son état actuel.")
    if need.opens_at and at < need.opens_at:
        raise ValidationError("Ce besoin n'est pas encore ouvert.")
    if need.closes_at and at >= need.closes_at:
        raise ValidationError("Ce besoin est arrivé à échéance.")


def _profile_is_searchable(user) -> bool:
    profile = getattr(user, "profile", None)
    return bool(profile and profile.public_profile and profile.searchable)


def _profile_open_to(user, match_kind: str) -> bool:
    return ProfileOpenTo.objects.filter(
        profile=user,
        kind=match_kind,
        is_active=True,
        is_searchable=True,
    ).exists()


def profile_is_eligible_for_need(*, need: ActionNeed, profile) -> bool:
    if need.candidate_kind == ActionNeedCandidateKind.SPACE:
        return False
    if not _profile_is_searchable(profile):
        return False
    return _profile_open_to(profile, need.match_kind)


def _space_is_publicly_discoverable(space: Organization) -> bool:
    return bool(space.public_profile)


def _space_open_to(space: Organization, match_kind: str) -> bool:
    return SpaceOpenTo.objects.filter(
        space=space,
        kind=match_kind,
        is_active=True,
        is_searchable=True,
    ).exists()


def space_is_eligible_for_need(*, need: ActionNeed, space: Organization) -> bool:
    if need.candidate_kind == ActionNeedCandidateKind.PROFILE:
        return False
    if not _space_is_publicly_discoverable(space):
        return False
    return _space_open_to(space, need.match_kind)


def _subjects_are_blocked(*, need: ActionNeed, candidate_profile=None, candidate_space=None) -> bool:
    if need.owner_profile_id:
        if candidate_profile is not None:
            return ActionBlock.objects.filter(
                Q(owner_profile=need.owner_profile, blocked_profile=candidate_profile)
                | Q(owner_profile=candidate_profile, blocked_profile=need.owner_profile)
            ).exists()
        if candidate_space is not None:
            return ActionBlock.objects.filter(
                Q(owner_profile=need.owner_profile, blocked_space=candidate_space)
                | Q(owner_space=candidate_space, blocked_profile=need.owner_profile)
            ).exists()
    if need.space_id:
        if candidate_profile is not None:
            return ActionBlock.objects.filter(
                Q(owner_space=need.space, blocked_profile=candidate_profile)
                | Q(owner_profile=candidate_profile, blocked_space=need.space)
            ).exists()
        if candidate_space is not None:
            return ActionBlock.objects.filter(
                Q(owner_space=need.space, blocked_space=candidate_space)
                | Q(owner_space=candidate_space, blocked_space=need.space)
            ).exists()
    return False


def _emit_need_event(*, need: ActionNeed, event_type: str, suffix: str) -> None:
    emit_domain_event(
        event_type=event_type,
        aggregate_type="action_need",
        aggregate_id=need.pk,
        payload={"status": need.status, "match_kind": need.match_kind},
        idempotency_key=f"action-need:{need.pk}:{suffix}",
    )


def _emit_proposal_event(*, proposal: ActionProposal, event_type: str, suffix: str) -> None:
    emit_domain_event(
        event_type=event_type,
        aggregate_type="action_proposal",
        aggregate_id=proposal.pk,
        payload={"status": proposal.status, "action_need_id": str(proposal.need_id)},
        idempotency_key=f"action-proposal:{proposal.pk}:{suffix}",
    )


@transaction.atomic
def create_action_need(
    *, actor, title: str, match_kind: str, owner_profile=None, space=None, description="",
    candidate_kind=ActionNeedCandidateKind.ANY, activity=None, occurrence=None, opportunity=None,
    visibility=ActionNeedVisibility.NETWORK, intake_policy=ActionNeedIntakePolicy.OPEN,
    target_count=1, opens_at=None, closes_at=None, needed_from=None, needed_until=None,
) -> ActionNeed:
    _require_need_owner(actor, owner_profile=owner_profile, space=space)
    _normalize_kind(match_kind)
    if candidate_kind not in ActionNeedCandidateKind.values:
        raise ValidationError({"candidate_kind": "Type de candidat invalide."})
    if visibility not in ActionNeedVisibility.values:
        raise ValidationError({"visibility": "Visibilité invalide."})
    if intake_policy not in ActionNeedIntakePolicy.values:
        raise ValidationError({"intake_policy": "Politique de proposition invalide."})
    if target_count < 1:
        raise ValidationError({"target_count": "Le besoin doit viser au moins une contribution."})
    if opens_at and closes_at and opens_at >= closes_at:
        raise ValidationError({"closes_at": "La fermeture doit suivre l'ouverture."})
    if needed_from and needed_until and needed_from >= needed_until:
        raise ValidationError({"needed_until": "La fin du besoin doit suivre son début."})

    need = ActionNeed.objects.create(
        owner_profile=owner_profile,
        space=space,
        created_by=actor,
        title=(title or "").strip(),
        description=(description or "").strip(),
        match_kind=match_kind,
        candidate_kind=candidate_kind,
        activity=activity,
        occurrence=occurrence,
        opportunity=opportunity,
        visibility=visibility,
        intake_policy=intake_policy,
        target_count=target_count,
        opens_at=opens_at,
        closes_at=closes_at,
        needed_from=needed_from,
        needed_until=needed_until,
        status=ActionNeedStatus.OPEN,
    )
    need.full_clean()
    _emit_need_event(need=need, event_type=DomainEventType.ACTION_NEED_CREATED, suffix="created")
    return need


@transaction.atomic
def transition_action_need(*, actor, need: ActionNeed, status: str) -> ActionNeed:
    locked = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity", "occurrence"
    ).get(pk=need.pk)
    if not can_manage_action_need(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas modifier ce besoin.")
    allowed = {
        ActionNeedStatus.OPEN: {ActionNeedStatus.PAUSED, ActionNeedStatus.FULFILLED, ActionNeedStatus.CANCELLED},
        ActionNeedStatus.PAUSED: {ActionNeedStatus.OPEN, ActionNeedStatus.CANCELLED},
    }
    if status not in allowed.get(locked.status, set()):
        raise ValidationError({"status": "Transition de besoin invalide."})
    previous_status = locked.status
    locked.status = status
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "updated_at"])
    event_type = {
        ActionNeedStatus.PAUSED: DomainEventType.ACTION_NEED_PAUSED,
        ActionNeedStatus.OPEN: DomainEventType.ACTION_NEED_REOPENED,
        ActionNeedStatus.FULFILLED: DomainEventType.ACTION_NEED_FULFILLED,
        ActionNeedStatus.CANCELLED: DomainEventType.ACTION_NEED_CANCELLED,
    }[status]
    _emit_need_event(
        need=locked,
        event_type=event_type,
        suffix=f"{previous_status}-to-{status}:{locked.updated_at.isoformat()}",
    )
    return locked


def close_action_need(*, actor, need: ActionNeed) -> ActionNeed:
    """Compatibility operation: a manual close is an explicit cancellation."""
    return transition_action_need(actor=actor, need=need, status=ActionNeedStatus.CANCELLED)


@transaction.atomic
def expire_action_need(*, need: ActionNeed, at=None) -> ActionNeed:
    """Expire a due Need without inventing an actor for scheduled automation."""

    at = at or timezone.now()
    locked = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity", "occurrence"
    ).get(pk=need.pk)
    if locked.status not in {ActionNeedStatus.OPEN, ActionNeedStatus.PAUSED}:
        return locked
    if not locked.closes_at or at < locked.closes_at:
        return locked
    previous_status = locked.status
    locked.status = ActionNeedStatus.EXPIRED
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "updated_at"])
    _emit_need_event(
        need=locked,
        event_type=DomainEventType.ACTION_NEED_EXPIRED,
        suffix=f"{previous_status}-to-expired:{locked.updated_at.isoformat()}",
    )
    return locked


@transaction.atomic
def create_action_proposal(
    *, actor, need: ActionNeed, candidate_profile=None, candidate_space=None,
    direction=ActionProposalDirection.OWNER_TO_CANDIDATE, message="", client_reference=None,
) -> ActionProposal:
    locked_need = ActionNeed.objects.select_for_update(of=("self",)).select_related(
        "owner_profile", "space", "activity", "activity__space", "occurrence", "created_by"
    ).get(pk=need.pk)
    _need_accepts_new_proposals(locked_need)
    if bool(candidate_profile) == bool(candidate_space):
        raise ValidationError("Une proposition vise soit un Profile, soit un Space.")
    if _subjects_are_blocked(need=locked_need, candidate_profile=candidate_profile, candidate_space=candidate_space):
        raise ValidationError("Cette mise en relation n'est pas disponible.")

    if direction == ActionProposalDirection.OWNER_TO_CANDIDATE:
        if not can_manage_action_need(actor, locked_need):
            raise PermissionDenied("Vous ne pouvez pas solliciter de candidat pour ce besoin.")
        if candidate_profile is not None and not profile_is_eligible_for_need(need=locked_need, profile=candidate_profile):
            raise ValidationError("Ce Profile n'est pas découvrable pour ce besoin selon ses réglages actuels.")
        if candidate_space is not None and not space_is_eligible_for_need(need=locked_need, space=candidate_space):
            raise ValidationError("Ce Space n'est pas découvrable pour ce besoin selon ses réglages actuels.")
    elif direction == ActionProposalDirection.CANDIDATE_TO_OWNER:
        if locked_need.visibility == ActionNeedVisibility.PRIVATE:
            raise ValidationError("Ce besoin privé n'accepte pas de proposition spontanée.")
        if locked_need.intake_policy == ActionNeedIntakePolicy.INVITE_ONLY:
            raise ValidationError("Ce besoin fonctionne uniquement sur invitation.")
        _require_candidate_authority(actor=actor, candidate_profile=candidate_profile, candidate_space=candidate_space)
        if locked_need.intake_policy == ActionNeedIntakePolicy.MATCHED:
            if candidate_profile is not None and not profile_is_eligible_for_need(need=locked_need, profile=candidate_profile):
                raise ValidationError("Ce besoin est réservé aux Profiles compatibles présentés par Makolo.")
            if candidate_space is not None and not space_is_eligible_for_need(need=locked_need, space=candidate_space):
                raise ValidationError("Ce besoin est réservé aux Spaces compatibles présentés par Makolo.")
    else:
        raise ValidationError({"direction": "Direction de proposition invalide."})

    normalized_message = (message or "").strip()
    normalized_reference = (client_reference or "").strip() or None
    if normalized_reference:
        existing = ActionProposal.objects.filter(client_reference=normalized_reference).first()
        if existing:
            same_candidate = (
                existing.candidate_profile_id == getattr(candidate_profile, "pk", None)
                and existing.candidate_space_id == getattr(candidate_space, "pk", None)
            )
            if existing.need_id == locked_need.pk and existing.direction == direction and same_candidate:
                return existing
            raise ValidationError({"client_reference": "Cette référence client appartient à une autre proposition."})

    try:
        proposal = ActionProposal.objects.create(
            need=locked_need,
            direction=direction,
            candidate_profile=candidate_profile,
            candidate_space=candidate_space,
            created_by=actor,
            message=normalized_message,
            client_reference=normalized_reference,
            status=ActionProposalStatus.PENDING,
        )
    except IntegrityError:
        if normalized_reference:
            existing = ActionProposal.objects.filter(client_reference=normalized_reference).first()
            if existing and existing.need_id == locked_need.pk:
                return existing
        raise
    proposal.full_clean()
    _emit_proposal_event(
        proposal=proposal,
        event_type=DomainEventType.ACTION_PROPOSAL_CREATED,
        suffix="created",
    )
    return proposal


@transaction.atomic
def respond_to_action_proposal(*, actor, proposal: ActionProposal, status: str, response_message="") -> ActionProposal:
    if status not in {ActionProposalStatus.ACCEPTED, ActionProposalStatus.DECLINED}:
        raise ValidationError({"status": "Réponse de proposition invalide."})
    locked = ActionProposal.objects.select_for_update().select_related(
        "need", "need__owner_profile", "need__space", "candidate_profile", "candidate_space"
    ).get(pk=proposal.pk)
    if locked.status != ActionProposalStatus.PENDING:
        if locked.status == status:
            return locked
        raise ValidationError({"status": "Cette proposition a déjà reçu une réponse."})
    if locked.need.status not in ACTIVE_NEED_STATUSES:
        raise ValidationError("Le besoin lié n'est plus actif.")

    if locked.direction == ActionProposalDirection.OWNER_TO_CANDIDATE:
        _require_candidate_authority(
            actor=actor,
            candidate_profile=locked.candidate_profile,
            candidate_space=locked.candidate_space,
        )
    else:
        if not can_manage_action_need(actor, locked.need):
            raise PermissionDenied("Vous ne pouvez pas répondre à cette proposition.")

    locked.status = status
    locked.response_message = (response_message or "").strip()
    locked.responded_by = actor
    locked.responded_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "response_message", "responded_by", "responded_at", "updated_at"])
    event_type = (
        DomainEventType.ACTION_PROPOSAL_ACCEPTED
        if status == ActionProposalStatus.ACCEPTED
        else DomainEventType.ACTION_PROPOSAL_DECLINED
    )
    _emit_proposal_event(
        proposal=locked,
        event_type=event_type,
        suffix=f"{status}:{locked.responded_at.isoformat()}",
    )
    return locked


@transaction.atomic
def withdraw_action_proposal(*, actor, proposal: ActionProposal) -> ActionProposal:
    locked = ActionProposal.objects.select_for_update().select_related("need").get(pk=proposal.pk)
    if locked.status != ActionProposalStatus.PENDING:
        raise ValidationError({"status": "Seule une proposition en attente peut être retirée."})
    if locked.created_by_id != actor.pk:
        raise PermissionDenied("Vous ne pouvez retirer que votre propre proposition.")
    locked.status = ActionProposalStatus.WITHDRAWN
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "updated_at"])
    _emit_proposal_event(
        proposal=locked,
        event_type=DomainEventType.ACTION_PROPOSAL_WITHDRAWN,
        suffix=f"withdrawn:{locked.updated_at.isoformat()}",
    )
    return locked


def create_profile_solicitation(*, actor, profile, **kwargs) -> ActionProposal:
    """Compatibility wrapper for the G6 Profile solicitation action."""

    need = create_action_need(actor=actor, owner_profile=actor, **kwargs)
    return create_action_proposal(
        actor=actor,
        need=need,
        candidate_profile=profile,
        direction=ActionProposalDirection.OWNER_TO_CANDIDATE,
    )


def respond_to_profile_solicitation(*, actor, solicitation: ActionProposal, status: str) -> ActionProposal:
    return respond_to_action_proposal(actor=actor, proposal=solicitation, status=status)


def block_action_subject(*, actor, owner_profile=None, owner_space=None, blocked_profile=None, blocked_space=None, reason="") -> ActionBlock:
    if bool(owner_profile) == bool(owner_space):
        raise ValidationError("Le blocage appartient soit à un Profile, soit à un Space.")
    if bool(blocked_profile) == bool(blocked_space):
        raise ValidationError("Le blocage vise soit un Profile, soit un Space.")
    if owner_profile is not None and owner_profile.pk != actor.pk:
        raise PermissionDenied("Vous ne pouvez créer un blocage que pour votre propre Profile.")
    if owner_space is not None and not can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=owner_space):
        raise PermissionDenied("Ce blocage Space exige l'autorité de gestion du réseau d'action.")
    if owner_profile_id := getattr(owner_profile, "pk", None):
        if owner_profile_id == getattr(blocked_profile, "pk", None):
            raise ValidationError("Un Profile ne peut pas se bloquer lui-même.")
    if owner_space_id := getattr(owner_space, "pk", None):
        if owner_space_id == getattr(blocked_space, "pk", None):
            raise ValidationError("Un Space ne peut pas se bloquer lui-même.")

    block = ActionBlock.objects.create(
        owner_profile=owner_profile,
        owner_space=owner_space,
        blocked_profile=blocked_profile,
        blocked_space=blocked_space,
        reason=ActionBlockReason.MANUAL,
        note=(reason or "").strip(),
        created_by=actor,
    )
    block.full_clean()
    return block

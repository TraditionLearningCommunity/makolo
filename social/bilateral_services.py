from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import (
    ActionNeed,
    ActionNeedIntakePolicy,
    ActionNeedStatus,
    ActionNeedVisibility,
    ActionNetworkBlock,
    ActionProposal,
    ActionProposalDirection,
    ActionProposalStatus,
)
from .profile_search import profile_is_eligible_for_need, space_is_eligible_for_need


def _authenticated(actor) -> bool:
    return bool(actor and getattr(actor, "is_authenticated", False))


def can_manage_action_need(actor, need: ActionNeed) -> bool:
    """Resolve authority from personal ownership or canonical Mandates."""

    if not _authenticated(actor):
        return False
    if getattr(actor, "is_superuser", False):
        return True
    if need.owner_profile_id:
        if need.owner_profile_id != actor.pk:
            return False
        if need.activity_id:
            return need.activity.owner_profile_id == actor.pk
        return True
    if not need.space_id:
        return False
    if need.activity_id:
        return need.activity.space_id == need.space_id and can(
            actor, PermissionCode.ACTIVITY_MANAGE, activity=need.activity
        )
    return can(actor, PermissionCode.SPACE_MANAGE, space=need.space)


def _require_need_authority(*, actor, owner_profile=None, space=None, activity=None, occurrence=None) -> None:
    if not _authenticated(actor):
        raise PermissionDenied("Connectez-vous pour gérer un besoin.")
    if bool(owner_profile) == bool(space):
        raise ValidationError("Un besoin appartient soit à un Profile, soit à un Space.")
    if occurrence is not None:
        if activity is None or occurrence.activity_id != activity.pk:
            raise ValidationError({"occurrence": "L'Occurrence doit appartenir à l'Activity du besoin."})
    if owner_profile is not None:
        if owner_profile.pk != actor.pk:
            raise PermissionDenied("Vous ne pouvez créer qu'un besoin personnel pour votre propre Profile.")
        if activity is not None and activity.owner_profile_id != actor.pk:
            raise PermissionDenied("Cette Activity n'appartient pas à votre contexte personnel.")
        return
    if activity is not None:
        if activity.space_id != space.pk:
            raise ValidationError({"activity": "L'Activity doit appartenir au Space du besoin."})
        if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            raise PermissionDenied("Cette Activity exige l'autorité ACTIVITY_MANAGE.")
        return
    if not can(actor, PermissionCode.SPACE_MANAGE, space=space):
        raise PermissionDenied("Ce besoin Space exige l'autorité SPACE_MANAGE.")


def _need_accepts_new_proposals(need: ActionNeed) -> None:
    if need.status != ActionNeedStatus.OPEN:
        raise ValidationError("Une nouvelle proposition exige un besoin ouvert.")
    now = timezone.now()
    if need.opens_at and now < need.opens_at:
        raise ValidationError("Ce besoin n'accepte pas encore de propositions.")
    if need.closes_at and now > need.closes_at:
        raise ValidationError("La fenêtre de proposition de ce besoin est terminée.")


def _subjects_are_blocked(*, need: ActionNeed, candidate_profile=None, candidate_space=None) -> bool:
    if need.owner_profile_id and candidate_profile is not None:
        return ActionNetworkBlock.objects.filter(
            blocker_profile_id=need.owner_profile_id,
            blocked_profile=candidate_profile,
        ).exists() or ActionNetworkBlock.objects.filter(
            blocker_profile=candidate_profile,
            blocked_profile_id=need.owner_profile_id,
        ).exists()
    if need.owner_profile_id and candidate_space is not None:
        return ActionNetworkBlock.objects.filter(
            blocker_profile_id=need.owner_profile_id,
            blocked_space=candidate_space,
        ).exists() or ActionNetworkBlock.objects.filter(
            blocker_space=candidate_space,
            blocked_profile_id=need.owner_profile_id,
        ).exists()
    if need.space_id and candidate_profile is not None:
        return ActionNetworkBlock.objects.filter(
            blocker_space_id=need.space_id,
            blocked_profile=candidate_profile,
        ).exists() or ActionNetworkBlock.objects.filter(
            blocker_profile=candidate_profile,
            blocked_space_id=need.space_id,
        ).exists()
    if need.space_id and candidate_space is not None:
        return ActionNetworkBlock.objects.filter(
            blocker_space_id=need.space_id,
            blocked_space=candidate_space,
        ).exists() or ActionNetworkBlock.objects.filter(
            blocker_space=candidate_space,
            blocked_space_id=need.space_id,
        ).exists()
    return False


def _require_candidate_authority(*, actor, candidate_profile=None, candidate_space=None) -> None:
    if candidate_profile is not None:
        if getattr(actor, "pk", None) != candidate_profile.pk:
            raise PermissionDenied("Seul le Profile candidat peut agir pour cette proposition.")
        return
    if candidate_space is not None:
        if not can(actor, PermissionCode.SPACE_MANAGE, space=candidate_space):
            raise PermissionDenied("Cette proposition exige l'autorité du Space candidat.")
        return
    raise ValidationError("Un candidat est obligatoire.")


@transaction.atomic
def create_action_need(
    *, actor, title, match_kind=None, open_to_kind=None, description="", owner_profile=None, space=None,
    topics=(), activity=None, occurrence=None, opportunity=None, candidate_kind="profile",
    visibility="private", intake_policy="invite_only", target_count=None,
    opens_at=None, closes_at=None, needed_from=None, needed_until=None,
) -> ActionNeed:
    _require_need_authority(
        actor=actor,
        owner_profile=owner_profile,
        space=space,
        activity=activity,
        occurrence=occurrence,
    )
    effective_match_kind = match_kind or open_to_kind
    if not effective_match_kind:
        raise ValidationError({"match_kind": "La famille de matching est obligatoire."})
    need = ActionNeed(
        owner_profile=owner_profile,
        space=space,
        created_by=actor,
        title=title,
        description=description,
        match_kind=effective_match_kind,
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
    need.save()
    if topics:
        need.topics.set(topics)
    return need


@transaction.atomic
def transition_action_need(*, actor, need: ActionNeed, status: str) -> ActionNeed:
    allowed = {
        ActionNeedStatus.DRAFT: {ActionNeedStatus.OPEN, ActionNeedStatus.CANCELLED},
        ActionNeedStatus.OPEN: {ActionNeedStatus.PAUSED, ActionNeedStatus.FILLED, ActionNeedStatus.CANCELLED, ActionNeedStatus.EXPIRED},
        ActionNeedStatus.PAUSED: {ActionNeedStatus.OPEN, ActionNeedStatus.FILLED, ActionNeedStatus.CANCELLED, ActionNeedStatus.EXPIRED},
        ActionNeedStatus.FILLED: set(),
        ActionNeedStatus.CANCELLED: set(),
        ActionNeedStatus.EXPIRED: set(),
    }
    locked = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity", "occurrence"
    ).get(pk=need.pk)
    if not can_manage_action_need(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas changer l'état de ce besoin.")
    if locked.status == status:
        return locked
    if status not in allowed.get(locked.status, set()):
        raise ValidationError({"status": "Transition de besoin invalide."})
    locked.status = status
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "updated_at"])
    return locked


def close_action_need(*, actor, need: ActionNeed) -> ActionNeed:
    """Compatibility operation: a manual close is an explicit cancellation."""
    return transition_action_need(actor=actor, need=need, status=ActionNeedStatus.CANCELLED)


@transaction.atomic
def create_action_proposal(
    *, actor, need: ActionNeed, candidate_profile=None, candidate_space=None,
    direction=ActionProposalDirection.OWNER_TO_CANDIDATE, message="", client_reference=None,
) -> ActionProposal:
    locked_need = ActionNeed.objects.select_for_update().select_related(
        "owner_profile", "space", "activity", "occurrence", "created_by"
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
            if existing.need_id == locked_need.pk and existing.direction == direction and same_candidate and existing.message == normalized_message:
                return existing
            raise ValidationError("Cette référence d'idempotence est déjà utilisée pour une autre proposition.")

    try:
        proposal = ActionProposal.objects.create(
            need=locked_need,
            candidate_profile=candidate_profile,
            candidate_space=candidate_space,
            initiated_by=actor,
            direction=direction,
            message=normalized_message,
            client_reference=normalized_reference,
        )
    except IntegrityError as exc:
        raise ValidationError("Une proposition active existe déjà pour ce candidat et ce besoin.") from exc

    if direction == ActionProposalDirection.OWNER_TO_CANDIDATE and candidate_profile is not None:
        create_notification(
            recipient=candidate_profile,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Nouvelle proposition Makolo",
            message=f"{locked_need.owner_display_name} vous propose « {locked_need.title} ».",
            action_url=reverse("social:my-solicitations"),
            dedup_key=f"action-proposal:{proposal.pk}",
            metadata={"proposal_id": str(proposal.pk), "need_id": str(locked_need.pk)},
            queue_email=False,
        )
    elif direction == ActionProposalDirection.CANDIDATE_TO_OWNER:
        recipient = locked_need.owner_profile or locked_need.created_by
        if recipient and recipient.pk != actor.pk:
            create_notification(
                recipient=recipient,
                kind=NotificationKind.SYSTEM,
                category=NotificationCategory.SYSTEM,
                title="Nouvelle proposition pour votre besoin",
                message=f"Une proposition attend votre réponse pour « {locked_need.title} ».",
                action_url=reverse("social:need-detail", kwargs={"pk": locked_need.pk}),
                dedup_key=f"action-proposal-owner:{proposal.pk}",
                metadata={"proposal_id": str(proposal.pk), "need_id": str(locked_need.pk)},
                queue_email=False,
            )
    return proposal


@transaction.atomic
def respond_to_action_proposal(*, actor, proposal: ActionProposal, status: str, response_message="") -> ActionProposal:
    if status not in {ActionProposalStatus.ACCEPTED, ActionProposalStatus.DECLINED}:
        raise ValidationError({"status": "Réponse de proposition invalide."})
    locked = ActionProposal.objects.select_for_update().select_related(
        "candidate_profile", "candidate_space", "initiated_by", "need", "need__space", "need__owner_profile", "need__activity", "need__occurrence"
    ).get(pk=proposal.pk)
    if locked.status != ActionProposalStatus.PENDING:
        raise ValidationError("Cette proposition n'est plus en attente.")
    if locked.expires_at and timezone.now() >= locked.expires_at:
        locked.status = ActionProposalStatus.EXPIRED
        locked._allow_status_transition = True
        locked.save(update_fields=["status", "updated_at"])
        raise ValidationError("Cette proposition a expiré.")

    if locked.direction == ActionProposalDirection.OWNER_TO_CANDIDATE:
        _require_candidate_authority(actor=actor, candidate_profile=locked.candidate_profile, candidate_space=locked.candidate_space)
    else:
        if not can_manage_action_need(actor, locked.need):
            raise PermissionDenied("Seul le propriétaire autorisé du besoin peut répondre à cette proposition.")

    locked.status = status
    locked.response_message = (response_message or "").strip()
    locked.responded_by = actor
    locked.responded_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "response_message", "responded_by", "responded_at", "updated_at"])

    if status == ActionProposalStatus.ACCEPTED:
        try:
            from activities.involvement_services import realize_activity_proposal
        except ImportError:
            realize_activity_proposal = None
        if realize_activity_proposal is not None:
            realize_activity_proposal(actor=actor, proposal=locked)

    recipient = locked.initiated_by
    if recipient_id := getattr(recipient, "pk", None):
        if recipient_id != getattr(actor, "pk", None):
            verb = "acceptée" if status == ActionProposalStatus.ACCEPTED else "refusée"
            create_notification(
                recipient=recipient,
                kind=NotificationKind.SYSTEM,
                category=NotificationCategory.SYSTEM,
                title="Réponse à une proposition Makolo",
                message=f"La proposition « {locked.need.title} » a été {verb}.",
                action_url=reverse("social:need-detail", kwargs={"pk": locked.need_id}),
                dedup_key=f"action-proposal-response:{locked.pk}:{status}",
                metadata={"proposal_id": str(locked.pk), "need_id": str(locked.need_id), "status": status},
                queue_email=False,
            )
    return locked


@transaction.atomic
def cancel_action_proposal(*, actor, proposal: ActionProposal) -> ActionProposal:
    locked = ActionProposal.objects.select_for_update().get(pk=proposal.pk)
    if locked.initiated_by_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul l'initiateur peut annuler cette proposition.")
    if locked.status != ActionProposalStatus.PENDING:
        raise ValidationError("Seule une proposition en attente peut être annulée.")
    locked.status = ActionProposalStatus.CANCELLED
    locked.cancelled_by = actor
    locked.cancelled_at = timezone.now()
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])
    return locked


@transaction.atomic
def create_action_network_block(
    *, actor, blocker_profile=None, blocker_space=None, blocked_profile=None, blocked_space=None,
) -> ActionNetworkBlock:
    if bool(blocker_profile) == bool(blocker_space) or bool(blocked_profile) == bool(blocked_space):
        raise ValidationError("Un bloc exige exactement un sujet de chaque côté.")
    if blocker_profile is not None:
        if blocker_profile.pk != getattr(actor, "pk", None):
            raise PermissionDenied("Un Profile ne peut créer qu'un bloc en son propre nom.")
    elif not can(actor, PermissionCode.SPACE_MANAGE, space=blocker_space):
        raise PermissionDenied("Vous n'êtes pas autorisé à bloquer au nom de ce Space.")
    try:
        return ActionNetworkBlock.objects.create(
            blocker_profile=blocker_profile,
            blocker_space=blocker_space,
            blocked_profile=blocked_profile,
            blocked_space=blocked_space,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise ValidationError("Ce bloc existe déjà.") from exc


# Compatibility wrappers for the previous G7 API.
def create_profile_solicitation(*, actor, need: ActionNeed, recipient_profile, message="") -> ActionProposal:
    return create_action_proposal(
        actor=actor,
        need=need,
        candidate_profile=recipient_profile,
        direction=ActionProposalDirection.OWNER_TO_CANDIDATE,
        message=message,
    )


def respond_to_profile_solicitation(*, actor, solicitation: ActionProposal, status: str) -> ActionProposal:
    return respond_to_action_proposal(actor=actor, proposal=solicitation, status=status)


def cancel_profile_solicitation(*, actor, solicitation: ActionProposal) -> ActionProposal:
    return cancel_action_proposal(actor=actor, proposal=solicitation)

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import GroupMembership, GroupMembershipStatus
from groups.services import has_group_permission
from journeys.models import Journey, JourneyStatus

from .models import Contribution, ContributionKind, ContributionStatus, ContributionVisibility


PARTICIPATION_JOURNEY_STATUSES = {
    JourneyStatus.CONFIRMED,
    JourneyStatus.IN_PROGRESS,
    JourneyStatus.FULFILLED,
}
DISQUALIFYING_ACCESS_STATUSES = {
    AccessStatus.CANCELLED,
    AccessStatus.REVOKED,
    AccessStatus.TRANSFERRED,
}


def _authenticated(actor) -> bool:
    return bool(getattr(actor, "is_authenticated", False))


def _active_group_member(actor, group) -> bool:
    return bool(
        _authenticated(actor)
        and GroupMembership.objects.filter(
            group=group,
            profile=actor,
            status=GroupMembershipStatus.ACTIVE,
        ).exists()
    )


def _can_contribute_to_group(actor, group) -> bool:
    return _active_group_member(actor, group) or has_group_permission(
        actor, PermissionCode.GROUP_MANAGE, group
    )


def _can_manage_activity(actor, activity) -> bool:
    return bool(activity and _authenticated(actor) and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity))


def _can_manage_space(actor, space) -> bool:
    return bool(space and _authenticated(actor) and can(actor, PermissionCode.SPACE_MANAGE, space=space))


def _has_activity_relation(actor, activity, *, occurrence=None) -> bool:
    if not (_authenticated(actor) and activity):
        return False
    journeys = Journey.objects.filter(
        beneficiary=actor,
        activity=activity,
        status__in=PARTICIPATION_JOURNEY_STATUSES,
    )
    if occurrence is not None:
        journeys = journeys.filter(occurrence=occurrence)
    if journeys.exists():
        return True
    accesses = Access.objects.filter(beneficiary=actor, activity=activity).exclude(
        status__in=DISQUALIFYING_ACCESS_STATUSES
    )
    if occurrence is not None:
        accesses = accesses.filter(occurrence=occurrence)
    return accesses.exists()


def _require_publish_permission(*, actor, kind, group=None, space=None, activity=None, occurrence=None):
    if not _authenticated(actor):
        raise PermissionDenied("Connectez-vous pour contribuer.")

    if kind == ContributionKind.UPDATE:
        if _can_manage_activity(actor, activity) or _can_manage_space(actor, space):
            return
        raise PermissionDenied("Une mise à jour officielle exige l'autorité réelle sur ce contexte.")

    if group is not None:
        if not _can_contribute_to_group(actor, group):
            raise PermissionDenied("Vous devez être membre autorisé de ce Groupe pour contribuer.")
        if kind == ContributionKind.FIELD_NOTE and occurrence is None:
            raise ValidationError({"occurrence": "Une note terrain doit cibler une Occurrence."})
        return

    if kind == ContributionKind.SHARE:
        raise ValidationError("Un partage interne doit cibler un Groupe.")

    if kind == ContributionKind.FIELD_NOTE and occurrence is None:
        raise ValidationError({"occurrence": "Une note terrain doit cibler une Occurrence."})

    if _can_manage_activity(actor, activity) or _can_manage_space(actor, space):
        return
    if activity and _has_activity_relation(actor, activity, occurrence=occurrence):
        return
    raise PermissionDenied("Cette Contribution exige une relation réelle avec le contexte.")


def _public_visibility_allowed(*, kind, space=None, activity=None) -> bool:
    if kind != ContributionKind.UPDATE:
        return False
    if activity is not None:
        return activity.status == ActivityStatus.PUBLISHED and activity.visibility == ActivityVisibility.PUBLIC
    return bool(space and space.public_profile)


@transaction.atomic
def create_contribution(
    *,
    actor,
    kind,
    body="",
    space=None,
    group=None,
    activity=None,
    occurrence=None,
    parent=None,
    visibility=None,
) -> Contribution:
    if kind not in ContributionKind.values:
        raise ValidationError({"kind": "Type de Contribution inconnu."})

    if parent is not None:
        parent = Contribution.objects.select_for_update().select_related(
            "space", "group", "activity", "occurrence", "parent"
        ).get(pk=parent.pk)
        if parent.parent_id:
            raise ValidationError({"parent": "La profondeur maximale de discussion est atteinte."})
        if parent.status != ContributionStatus.PUBLISHED:
            raise ValidationError({"parent": "Cette discussion n'accepte plus de réponses."})
        space, group, activity, occurrence = parent.space, parent.group, parent.activity, parent.occurrence
        visibility = parent.visibility
        kind = ContributionKind.DISCUSSION
    elif occurrence is not None:
        if activity is not None and occurrence.activity_id != activity.pk:
            raise ValidationError({"occurrence": "L'Occurrence doit appartenir à l'Activity indiquée."})
        activity = activity or occurrence.activity

    if activity is not None and space is None and activity.space_id:
        space = activity.space
    if group is not None and space is None and group.space_id:
        space = group.space

    if not any((space, group, activity, occurrence)):
        raise ValidationError({"activity": "Une Contribution doit être ancrée dans un contexte Makolo."})

    _require_publish_permission(
        actor=actor,
        kind=kind,
        group=group,
        space=space,
        activity=activity,
        occurrence=occurrence,
    )

    if group is not None:
        visibility = ContributionVisibility.CONTEXT
    elif visibility is None:
        visibility = ContributionVisibility.CONTEXT
    elif visibility == ContributionVisibility.PUBLIC and not _public_visibility_allowed(
        kind=kind, space=space, activity=activity
    ):
        raise PermissionDenied("Seules les mises à jour officielles d'un contexte public peuvent être publiques.")

    contribution = Contribution(
        author_profile=actor,
        kind=kind,
        body=(body or "").strip(),
        space=space,
        group=group,
        activity=activity,
        occurrence=occurrence,
        parent=parent,
        visibility=visibility,
    )
    contribution.full_clean()
    contribution.save()
    return contribution


@transaction.atomic
def share_activity_to_group(*, actor, group, activity, body="") -> Contribution:
    return create_contribution(
        actor=actor,
        kind=ContributionKind.SHARE,
        body=body,
        group=group,
        activity=activity,
        visibility=ContributionVisibility.CONTEXT,
    )


def can_view_contribution(viewer, contribution: Contribution) -> bool:
    if contribution.status != ContributionStatus.PUBLISHED:
        return False
    if contribution.group_id:
        return _can_contribute_to_group(viewer, contribution.group)
    if contribution.visibility == ContributionVisibility.PUBLIC:
        if contribution.activity_id:
            return (
                contribution.activity.status == ActivityStatus.PUBLISHED
                and contribution.activity.visibility == ActivityVisibility.PUBLIC
            )
        return bool(contribution.space_id and contribution.space.public_profile)
    if not _authenticated(viewer):
        return False
    if contribution.author_profile_id == viewer.pk:
        return True
    if _can_manage_activity(viewer, contribution.activity) or _can_manage_space(viewer, contribution.space):
        return True
    return bool(
        contribution.activity_id
        and _has_activity_relation(viewer, contribution.activity, occurrence=contribution.occurrence)
    )


def _can_moderate(actor, contribution: Contribution) -> bool:
    if not _authenticated(actor):
        return False
    if getattr(actor, "is_staff", False):
        return True
    if contribution.group_id and has_group_permission(actor, PermissionCode.GROUP_MANAGE, contribution.group):
        return True
    if _can_manage_activity(actor, contribution.activity) or _can_manage_space(actor, contribution.space):
        return True
    return False


@transaction.atomic
def moderate_contribution(*, actor, contribution, status, reason="") -> Contribution:
    if status not in {ContributionStatus.HIDDEN, ContributionStatus.REMOVED}:
        raise ValidationError({"status": "Transition de modération non autorisée."})
    locked = Contribution.objects.select_for_update().select_related(
        "author_profile", "group", "space", "activity", "occurrence"
    ).get(pk=contribution.pk)
    own_remove = locked.author_profile_id == getattr(actor, "pk", None) and status == ContributionStatus.REMOVED
    if not own_remove and not _can_moderate(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas modérer cette Contribution.")
    locked.status = status
    locked.moderated_by = actor
    locked.moderated_at = timezone.now()
    locked.moderation_reason = (reason or "").strip()[:280]
    locked._allow_status_transition = True
    locked.save(update_fields=["status", "moderated_by", "moderated_at", "moderation_reason", "updated_at"])
    return locked

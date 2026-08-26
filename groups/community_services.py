from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import can
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import (
    ActivityGroupEligibility,
    ActivityGroupEligibilityStatus,
    Group,
    GroupDiscoverability,
    GroupInvitation,
    GroupInvitationStatus,
    GroupJoinRequest,
    GroupJoinRequestStatus,
    GroupMembership,
    GroupMembershipPolicy,
    GroupMembershipSource,
    GroupMembershipStatus,
    GroupStatus,
)
from .services import has_group_permission


def _lock_group(group_or_pk) -> Group:
    pk = getattr(group_or_pk, "pk", group_or_pk)
    return (
        Group.objects.select_for_update()
        .select_related("space", "owner_profile")
        .order_by()
        .get(pk=pk)
    )


def _active_membership(profile, group) -> bool:
    return bool(
        getattr(profile, "is_authenticated", False)
        and GroupMembership.objects.filter(
            group=group,
            profile=profile,
            status=GroupMembershipStatus.ACTIVE,
        ).exists()
    )


def _pending_invitation_matches(profile, group) -> bool:
    if not getattr(profile, "is_authenticated", False):
        return False
    queryset = GroupInvitation.objects.filter(
        group=group,
        status=GroupInvitationStatus.PENDING,
        expires_at__gt=timezone.now(),
    )
    if queryset.filter(profile=profile).exists():
        return True
    email = (getattr(profile, "email", "") or "").strip().lower()
    return bool(
        email
        and getattr(profile, "email_verified", False)
        and queryset.filter(profile__isnull=True, email__iexact=email).exists()
    )


def can_view_community_group(profile, group: Group) -> bool:
    """Whether this authenticated Profile may learn this Group exists."""
    if not getattr(profile, "is_authenticated", False):
        return False
    if has_group_permission(profile, PermissionCode.GROUP_VIEW, group):
        return True
    if _active_membership(profile, group):
        return True
    if _pending_invitation_matches(profile, group):
        return True
    if group.status != GroupStatus.ACTIVE:
        return False
    return group.discoverability in {
        GroupDiscoverability.LISTED,
        GroupDiscoverability.UNLISTED,
    }


def group_owner_label(group: Group) -> str:
    if group.space_id:
        return group.space.name
    owner = group.owner_profile
    if not owner:
        return "Makolo"
    profile = getattr(owner, "profile", None)
    if profile and profile.public_profile and profile.searchable:
        return owner.full_name or owner.username
    return "Profil Makolo"


def _ensure_self_membership_allowed(group: Group, profile) -> GroupMembership | None:
    membership = (
        GroupMembership.objects.select_for_update()
        .filter(group=group, profile=profile)
        .order_by()
        .first()
    )
    if membership and membership.status in {
        GroupMembershipStatus.SUSPENDED,
        GroupMembershipStatus.REMOVED,
    }:
        raise PermissionDenied(
            "Cette appartenance ne peut pas être réactivée en libre-service."
        )
    return membership


def _activate_self_membership(*, membership, group, profile, source, now):
    if membership:
        if membership.status == GroupMembershipStatus.ACTIVE:
            return membership, False
        if membership.status in {
            GroupMembershipStatus.SUSPENDED,
            GroupMembershipStatus.REMOVED,
        }:
            raise PermissionDenied(
                "Cette appartenance ne peut pas être réactivée en libre-service."
            )
        membership.status = GroupMembershipStatus.ACTIVE
        membership.source = source
        membership.joined_at = now
        membership.verified_at = now
        membership.save(
            update_fields=[
                "status",
                "source",
                "joined_at",
                "verified_at",
                "updated_at",
            ]
        )
        return membership, False

    membership, created = GroupMembership.objects.select_for_update().get_or_create(
        group=group,
        profile=profile,
        defaults={
            "status": GroupMembershipStatus.ACTIVE,
            "source": source,
            "joined_at": now,
            "verified_at": now,
        },
    )
    if created or membership.status == GroupMembershipStatus.ACTIVE:
        return membership, created
    if membership.status in {
        GroupMembershipStatus.SUSPENDED,
        GroupMembershipStatus.REMOVED,
    }:
        raise PermissionDenied(
            "Cette appartenance ne peut pas être réactivée en libre-service."
        )
    membership.status = GroupMembershipStatus.ACTIVE
    membership.source = source
    membership.joined_at = now
    membership.verified_at = now
    membership.save(
        update_fields=[
            "status",
            "source",
            "joined_at",
            "verified_at",
            "updated_at",
        ]
    )
    return membership, False


@transaction.atomic
def join_group(*, profile, group) -> tuple[GroupMembership, bool]:
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour rejoindre ce Groupe.")
    locked_group = _lock_group(group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Ce Groupe est archivé.")
    if locked_group.membership_policy != GroupMembershipPolicy.OPEN:
        raise PermissionDenied("Ce Groupe ne permet pas l'adhésion directe.")
    membership = _ensure_self_membership_allowed(locked_group, profile)
    now = timezone.now()
    membership, created = _activate_self_membership(
        membership=membership,
        group=locked_group,
        profile=profile,
        source=GroupMembershipSource.SELF_JOIN,
        now=now,
    )
    GroupJoinRequest.objects.filter(
        group=locked_group,
        profile=profile,
        status=GroupJoinRequestStatus.PENDING,
    ).update(
        status=GroupJoinRequestStatus.CANCELLED,
        decided_at=now,
        updated_at=now,
    )
    return membership, created


@transaction.atomic
def request_to_join(*, profile, group, message="") -> tuple[GroupJoinRequest, bool]:
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour demander à rejoindre ce Groupe.")
    locked_group = _lock_group(group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Ce Groupe est archivé.")
    if locked_group.membership_policy != GroupMembershipPolicy.REQUEST:
        raise PermissionDenied("Ce Groupe n'accepte pas les demandes d'adhésion.")
    membership = _ensure_self_membership_allowed(locked_group, profile)
    if membership and membership.status == GroupMembershipStatus.ACTIVE:
        raise ValidationError("Vous êtes déjà membre actif de ce Groupe.")
    request, created = GroupJoinRequest.objects.select_for_update().get_or_create(
        group=locked_group,
        profile=profile,
        status=GroupJoinRequestStatus.PENDING,
        defaults={"message": (message or "").strip()[:500]},
    )
    return request, created


@transaction.atomic
def cancel_join_request(*, profile, request) -> GroupJoinRequest:
    locked = (
        GroupJoinRequest.objects.select_for_update()
        .select_related("group")
        .order_by()
        .get(pk=request.pk)
    )
    if locked.profile_id != getattr(profile, "pk", None):
        raise PermissionDenied("Cette demande ne vous appartient pas.")
    if locked.status == GroupJoinRequestStatus.CANCELLED:
        return locked
    if locked.status != GroupJoinRequestStatus.PENDING:
        raise ValidationError("Cette demande n'est plus annulable.")
    locked.status = GroupJoinRequestStatus.CANCELLED
    locked.decided_at = timezone.now()
    locked.save(update_fields=["status", "decided_at", "updated_at"])
    return locked


def _membership_from_approved_request(*, locked_group, profile, now):
    membership = (
        GroupMembership.objects.select_for_update()
        .filter(group=locked_group, profile=profile)
        .order_by()
        .first()
    )
    if membership and membership.status in {
        GroupMembershipStatus.SUSPENDED,
        GroupMembershipStatus.REMOVED,
    }:
        raise ValidationError(
            "Une appartenance suspendue ou retirée doit être réactivée explicitement par la gestion des membres."
        )
    if membership and membership.status == GroupMembershipStatus.ACTIVE:
        return membership
    if membership:
        membership.status = GroupMembershipStatus.ACTIVE
        membership.source = GroupMembershipSource.REQUEST
        membership.joined_at = now
        membership.verified_at = now
        membership.save(
            update_fields=[
                "status",
                "source",
                "joined_at",
                "verified_at",
                "updated_at",
            ]
        )
        return membership
    membership, _ = GroupMembership.objects.get_or_create(
        group=locked_group,
        profile=profile,
        defaults={
            "status": GroupMembershipStatus.ACTIVE,
            "source": GroupMembershipSource.REQUEST,
            "joined_at": now,
            "verified_at": now,
        },
    )
    if membership.status in {
        GroupMembershipStatus.SUSPENDED,
        GroupMembershipStatus.REMOVED,
    }:
        raise ValidationError(
            "Une appartenance suspendue ou retirée doit être réactivée explicitement par la gestion des membres."
        )
    return membership


@transaction.atomic
def approve_join_request(*, actor, request) -> tuple[GroupJoinRequest, GroupMembership]:
    locked_group = _lock_group(request.group_id)
    if not has_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group):
        raise PermissionDenied("Vous ne pouvez pas approuver les demandes de ce Groupe.")
    locked = (
        GroupJoinRequest.objects.select_for_update()
        .select_related("profile")
        .order_by()
        .get(pk=request.pk, group=locked_group)
    )
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Ce Groupe est archivé.")
    if locked.status == GroupJoinRequestStatus.APPROVED:
        membership = GroupMembership.objects.get(group=locked_group, profile=locked.profile)
        return locked, membership
    if locked.status != GroupJoinRequestStatus.PENDING:
        raise ValidationError("Cette demande n'est plus en attente.")
    now = timezone.now()
    membership = _membership_from_approved_request(
        locked_group=locked_group,
        profile=locked.profile,
        now=now,
    )
    locked.status = GroupJoinRequestStatus.APPROVED
    locked.decided_by = actor
    locked.decided_at = now
    locked.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    return locked, membership


@transaction.atomic
def reject_join_request(*, actor, request) -> GroupJoinRequest:
    locked_group = _lock_group(request.group_id)
    if not has_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group):
        raise PermissionDenied("Vous ne pouvez pas refuser les demandes de ce Groupe.")
    locked = GroupJoinRequest.objects.select_for_update().order_by().get(
        pk=request.pk,
        group=locked_group,
    )
    if locked.status == GroupJoinRequestStatus.REJECTED:
        return locked
    if locked.status != GroupJoinRequestStatus.PENDING:
        raise ValidationError("Cette demande n'est plus en attente.")
    locked.status = GroupJoinRequestStatus.REJECTED
    locked.decided_by = actor
    locked.decided_at = timezone.now()
    locked.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    return locked


def _activity_manager(actor, activity) -> bool:
    return bool(
        getattr(actor, "is_authenticated", False)
        and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
    )


def _current_usage_manager_mandates(group):
    conditions = Q(
        scope_type=AuthorityScope.GROUP,
        group=group,
        role__role_permissions__permission__code=PermissionCode.GROUP_MANAGE,
        role__role_permissions__permission__is_active=True,
    )
    if group.space_id:
        conditions |= Q(
            scope_type=AuthorityScope.SPACE,
            space_id=group.space_id,
            role__role_permissions__permission__code=PermissionCode.SPACE_GROUPS_MANAGE,
            role__role_permissions__permission__is_active=True,
        )
    return (
        Mandate.objects.filter(
            conditions,
            status=MandateStatus.ACTIVE,
            revoked_at__isnull=True,
            role__is_active=True,
        )
        .select_related("profile", "role")
        .distinct()
    )


def _notify_group_usage_request(eligibility):
    group = eligibility.group
    recipients = []
    if group.owner_profile_id:
        recipients.append(group.owner_profile)
    recipients.extend(
        mandate.profile
        for mandate in _current_usage_manager_mandates(group)
        if mandate.is_current()
    )
    unique = {recipient.pk: recipient for recipient in recipients if recipient}
    for recipient in unique.values():
        create_notification(
            recipient=recipient,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Demande d’utilisation d’un Groupe",
            message=(
                f"L’Activity « {eligibility.activity.title} » souhaite utiliser "
                f"le Groupe « {group.name} »."
            ),
            action_url=reverse(
                "groups:activity-eligibility-review",
                kwargs={"eligibility_id": eligibility.pk},
            ),
            dedup_key=f"group-eligibility-request:{eligibility.pk}:{recipient.pk}",
            queue_email=False,
            activity=eligibility.activity,
            metadata={
                "group_id": str(group.pk),
                "activity_id": str(eligibility.activity_id),
                "eligibility_id": str(eligibility.pk),
            },
        )


def _notify_group_usage_decision(eligibility):
    recipient = eligibility.requested_by
    if not recipient:
        return
    label = (
        "acceptée"
        if eligibility.status == ActivityGroupEligibilityStatus.APPROVED
        else "refusée"
    )
    create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title="Utilisation du Groupe mise à jour",
        message=f"La demande pour « {eligibility.group.name} » a été {label}.",
        action_url=reverse("groups:detail", kwargs={"slug": eligibility.group.slug}),
        dedup_key=f"group-eligibility-decision:{eligibility.pk}:{eligibility.status}",
        queue_email=False,
        activity=eligibility.activity,
        metadata={
            "group_id": str(eligibility.group_id),
            "activity_id": str(eligibility.activity_id),
            "eligibility_id": str(eligibility.pk),
            "status": eligibility.status,
        },
    )


@transaction.atomic
def request_activity_group_eligibility(
    *, actor, activity, group
) -> tuple[ActivityGroupEligibility, bool]:
    if not _activity_manager(actor, activity):
        raise PermissionDenied("Vous ne pouvez pas modifier l'éligibilité de cette Activity.")
    locked_group = _lock_group(group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Un Groupe archivé ne peut pas être utilisé par une Activity.")
    immediate = has_group_permission(actor, PermissionCode.GROUP_MANAGE, locked_group)
    now = timezone.now()
    relation, created = ActivityGroupEligibility.objects.select_for_update().get_or_create(
        group=locked_group,
        activity=activity,
        defaults={
            "status": (
                ActivityGroupEligibilityStatus.APPROVED
                if immediate
                else ActivityGroupEligibilityStatus.REQUESTED
            ),
            "requested_by": actor,
            "decided_by": actor if immediate else None,
            "requested_at": now,
            "decided_at": now if immediate else None,
        },
    )
    if not created and relation.status == ActivityGroupEligibilityStatus.APPROVED:
        return relation, False
    if not created:
        relation.requested_by = actor
        relation.requested_at = now
        relation.revoked_at = None
        if immediate:
            relation.status = ActivityGroupEligibilityStatus.APPROVED
            relation.decided_by = actor
            relation.decided_at = now
        else:
            relation.status = ActivityGroupEligibilityStatus.REQUESTED
            relation.decided_by = None
            relation.decided_at = None
        relation.save(
            update_fields=[
                "status",
                "requested_by",
                "requested_at",
                "decided_by",
                "decided_at",
                "revoked_at",
                "updated_at",
            ]
        )
    if not immediate:
        transaction.on_commit(
            lambda relation_id=relation.pk: _notify_group_usage_request(
                ActivityGroupEligibility.objects.select_related(
                    "group",
                    "group__owner_profile",
                    "activity",
                ).get(pk=relation_id)
            )
        )
    return relation, created


@transaction.atomic
def decide_activity_group_eligibility(*, actor, eligibility, approve: bool):
    locked = (
        ActivityGroupEligibility.objects.select_for_update()
        .select_related("group", "activity", "requested_by")
        .order_by()
        .get(pk=eligibility.pk)
    )
    if not has_group_permission(actor, PermissionCode.GROUP_MANAGE, locked.group):
        raise PermissionDenied("Vous ne pouvez pas autoriser l'utilisation de ce Groupe.")
    if approve and locked.group.status != GroupStatus.ACTIVE:
        raise ValidationError("Un Groupe archivé ne peut pas autoriser une nouvelle utilisation.")
    target = (
        ActivityGroupEligibilityStatus.APPROVED
        if approve
        else ActivityGroupEligibilityStatus.REJECTED
    )
    if locked.status == target:
        return locked
    if locked.status != ActivityGroupEligibilityStatus.REQUESTED:
        raise ValidationError("Cette demande d'utilisation n'est plus en attente.")
    locked.status = target
    locked.decided_by = actor
    locked.decided_at = timezone.now()
    locked.revoked_at = None
    locked.save(
        update_fields=[
            "status",
            "decided_by",
            "decided_at",
            "revoked_at",
            "updated_at",
        ]
    )
    transaction.on_commit(
        lambda relation_id=locked.pk: _notify_group_usage_decision(
            ActivityGroupEligibility.objects.select_related(
                "group",
                "activity",
                "requested_by",
            ).get(pk=relation_id)
        )
    )
    return locked


@transaction.atomic
def revoke_activity_group_eligibility(*, actor, eligibility):
    locked = (
        ActivityGroupEligibility.objects.select_for_update()
        .select_related("group", "activity")
        .order_by()
        .get(pk=eligibility.pk)
    )
    if not (
        has_group_permission(actor, PermissionCode.GROUP_MANAGE, locked.group)
        or _activity_manager(actor, locked.activity)
    ):
        raise PermissionDenied("Vous ne pouvez pas révoquer cette utilisation du Groupe.")
    if locked.status == ActivityGroupEligibilityStatus.REVOKED:
        return locked
    locked.status = ActivityGroupEligibilityStatus.REVOKED
    locked.revoked_at = timezone.now()
    locked.save(update_fields=["status", "revoked_at", "updated_at"])
    return locked


def profile_is_eligible_for_activity(profile, activity) -> bool:
    approved_group_ids = ActivityGroupEligibility.objects.filter(
        activity=activity,
        status=ActivityGroupEligibilityStatus.APPROVED,
    ).values_list("group_id", flat=True)
    if not approved_group_ids.exists():
        return True
    if not getattr(profile, "is_authenticated", False):
        return False
    return GroupMembership.objects.filter(
        group_id__in=approved_group_ids,
        profile=profile,
        status=GroupMembershipStatus.ACTIVE,
    ).exists()


def require_profile_activity_eligibility(profile, activity) -> None:
    if not profile_is_eligible_for_activity(profile, activity):
        raise ValidationError(
            "Cette Activity est réservée aux membres actifs d'un Groupe autorisé."
        )

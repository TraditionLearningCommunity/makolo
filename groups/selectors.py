from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import group_ids_with_permission, space_ids_with_permission

from .models import (
    ActivityGroupEligibility,
    ActivityGroupEligibilityStatus,
    Group,
    GroupInvitation,
    GroupInvitationStatus,
    GroupMembership,
    GroupMembershipStatus,
)
from .services import can_view_group, require_group_permission


def groups_for_profile(profile, *, space=None):
    queryset = Group.objects.select_related("space", "owner_profile", "created_by").annotate(
        active_member_count=Count(
            "memberships",
            filter=Q(memberships__status=GroupMembershipStatus.ACTIVE),
            distinct=True,
        )
    )
    if space is not None:
        queryset = queryset.filter(space=space)
    if not getattr(profile, "is_authenticated", False):
        return queryset.none()

    direct_ids = group_ids_with_permission(profile, PermissionCode.GROUP_VIEW)
    view_space_ids = space_ids_with_permission(profile, PermissionCode.SPACE_GROUPS_VIEW)
    manage_space_ids = space_ids_with_permission(profile, PermissionCode.SPACE_GROUPS_MANAGE)
    if direct_ids is None or view_space_ids is None or manage_space_ids is None:
        return queryset.order_by("name").distinct()

    filters = Q(owner_profile=profile) | Q(
        memberships__profile=profile,
        memberships__status=GroupMembershipStatus.ACTIVE,
    )
    if direct_ids:
        filters |= Q(pk__in=direct_ids)
    inherited_space_ids = set(view_space_ids) | set(manage_space_ids)
    if inherited_space_ids:
        filters |= Q(space_id__in=inherited_space_ids)
    return queryset.filter(filters).order_by("name").distinct()


def get_group_for_profile(profile, *, slug):
    group = Group.objects.select_related("space", "owner_profile", "created_by").get(slug=slug)
    if not can_view_group(profile, group):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Vous n'avez pas accès à ce Groupe.")
    return group


def group_members_for_admin(profile, group):
    require_group_permission(profile, PermissionCode.GROUP_MEMBERS_VIEW, group)
    return GroupMembership.objects.filter(group=group).select_related("profile").order_by(
        "profile__last_name",
        "profile__first_name",
        "profile__email",
    )


def pending_invitations_for_admin(profile, group):
    require_group_permission(profile, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
    return GroupInvitation.objects.filter(
        group=group,
        status=GroupInvitationStatus.PENDING,
    ).select_related("profile", "invited_by")


def direct_group_role_codes(profile, group):
    now = timezone.now()
    return list(
        Mandate.objects.filter(
            profile=profile,
            group=group,
            scope_type=AuthorityScope.GROUP,
            status=MandateStatus.ACTIVE,
            role__is_active=True,
            revoked_at__isnull=True,
        )
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .values_list("role__code", flat=True)
    )


def filter_queryset_by_activity_group_eligibility(
    queryset,
    profile,
    *,
    activity_id_field="activity_id",
):
    """Compose Group eligibility into any Activity-scoped read queryset.

    An Activity with no approved Group gate remains reachable. If at least one
    approved Group gate exists, an authenticated Profile must have an active
    membership in one of those approved Groups. No Discovery-owned eligibility
    state is introduced.
    """
    approved = ActivityGroupEligibility.objects.filter(
        activity_id=OuterRef(activity_id_field),
        status=ActivityGroupEligibilityStatus.APPROVED,
    )
    queryset = queryset.annotate(_has_group_gate=Exists(approved))
    if not getattr(profile, "is_authenticated", False):
        return queryset.filter(_has_group_gate=False)
    reachable = approved.filter(
        group__memberships__profile=profile,
        group__memberships__status=GroupMembershipStatus.ACTIVE,
    )
    return queryset.annotate(_group_reachable=Exists(reachable)).filter(
        Q(_has_group_gate=False) | Q(_group_reachable=True)
    )


def eligible_activity_ids_for_profile(profile, activity_ids):
    """Batch eligibility projection used by Activity-first recommendation reads."""
    ids = set(activity_ids)
    if not ids:
        return set()
    restricted = set(
        ActivityGroupEligibility.objects.filter(
            activity_id__in=ids,
            status=ActivityGroupEligibilityStatus.APPROVED,
        ).values_list("activity_id", flat=True)
    )
    if not restricted:
        return ids
    allowed = ids - restricted
    if not getattr(profile, "is_authenticated", False):
        return allowed
    allowed.update(
        ActivityGroupEligibility.objects.filter(
            activity_id__in=restricted,
            status=ActivityGroupEligibilityStatus.APPROVED,
            group__memberships__profile=profile,
            group__memberships__status=GroupMembershipStatus.ACTIVE,
        ).values_list("activity_id", flat=True)
    )
    return allowed

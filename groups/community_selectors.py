from django.db.models import Count, Q

from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode

from .community_services import can_view_community_group, group_owner_label
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
    GroupMembershipStatus,
    GroupStatus,
)
from .services import has_group_permission


def discoverable_groups(*, profile, query=""):
    if not getattr(profile, "is_authenticated", False):
        return Group.objects.none()
    queryset = (
        Group.objects.filter(
            status=GroupStatus.ACTIVE,
            discoverability=GroupDiscoverability.LISTED,
        )
        .select_related("space", "owner_profile", "owner_profile__profile")
        .annotate(
            active_member_count=Count(
                "memberships",
                filter=Q(memberships__status=GroupMembershipStatus.ACTIVE),
                distinct=True,
            )
        )
    )
    query = (query or "").strip()
    if query:
        owner_profile_filter = Q(
            owner_profile__profile__public_profile=True,
            owner_profile__profile__searchable=True,
        ) & (
            Q(owner_profile__first_name__icontains=query)
            | Q(owner_profile__last_name__icontains=query)
            | Q(owner_profile__username__icontains=query)
        )
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(space__name__icontains=query)
            | owner_profile_filter
        )
    return queryset.order_by("name", "id")


def community_group_or_none(*, profile, slug):
    group = (
        Group.objects.select_related(
            "space",
            "owner_profile",
            "owner_profile__profile",
            "created_by",
        )
        .filter(slug=slug)
        .first()
    )
    if group and can_view_community_group(profile, group):
        return group
    return None


def relationship_for_profile(*, profile, group):
    membership = GroupMembership.objects.filter(group=group, profile=profile).first()
    join_request = GroupJoinRequest.objects.filter(
        group=group,
        profile=profile,
        status=GroupJoinRequestStatus.PENDING,
    ).first()
    invitation = GroupInvitation.objects.filter(
        group=group,
        profile=profile,
        status=GroupInvitationStatus.PENDING,
    ).first()
    return membership, join_request, invitation


def pending_join_requests_for_admin(*, profile, group):
    if not has_group_permission(profile, PermissionCode.GROUP_MEMBERS_MANAGE, group):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Vous ne pouvez pas consulter les demandes de ce Groupe.")
    return (
        GroupJoinRequest.objects.filter(
            group=group,
            status=GroupJoinRequestStatus.PENDING,
        )
        .select_related("profile")
        .order_by("requested_at", "id")
    )


def approved_activities_for_group_viewer(*, profile, group):
    is_member = GroupMembership.objects.filter(
        group=group,
        profile=profile,
        status=GroupMembershipStatus.ACTIVE,
    ).exists()
    can_manage = has_group_permission(profile, PermissionCode.GROUP_MANAGE, group)
    if not (is_member or can_manage):
        return ActivityGroupEligibility.objects.none()
    return (
        ActivityGroupEligibility.objects.filter(
            group=group,
            status=ActivityGroupEligibilityStatus.APPROVED,
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility__in=[ActivityVisibility.PUBLIC, ActivityVisibility.UNLISTED],
        )
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity__title", "activity_id")
    )


def pending_activity_eligibilities_for_admin(*, profile, group):
    if not has_group_permission(profile, PermissionCode.GROUP_MANAGE, group):
        return ActivityGroupEligibility.objects.none()
    return (
        ActivityGroupEligibility.objects.filter(
            group=group,
            status=ActivityGroupEligibilityStatus.REQUESTED,
        )
        .select_related("activity", "requested_by")
        .order_by("requested_at", "id")
    )


def group_card(group):
    return {
        "group": group,
        "owner_label": group_owner_label(group),
    }

from django.db.models import Count, Q

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate
from authorization.services import group_ids_with_permission, space_ids_with_permission

from .models import (
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
    return list(
        Mandate.objects.filter(
            profile=profile,
            group=group,
            scope_type=AuthorityScope.GROUP,
            status="active",
            role__is_active=True,
            revoked_at__isnull=True,
        )
        .select_related("role")
        .values_list("role__code", flat=True)
    )

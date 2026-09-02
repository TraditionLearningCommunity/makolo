from django.core.exceptions import PermissionDenied

from groups.models import GroupMembership, GroupMembershipStatus
from groups.services import has_group_permission
from authorization.constants import PermissionCode

from .models import Contribution, ContributionStatus
from .services import can_view_contribution


SOCIAL_QUERY_LIMIT = 120


def _base_contributions():
    return Contribution.objects.select_related(
        "author_profile",
        "space",
        "group",
        "activity",
        "occurrence",
        "parent",
    ).filter(status=ContributionStatus.PUBLISHED)


def group_contributions(*, viewer, group, limit=50):
    allowed = has_group_permission(viewer, PermissionCode.GROUP_VIEW, group) or GroupMembership.objects.filter(
        group=group,
        profile=viewer,
        status=GroupMembershipStatus.ACTIVE,
    ).exists()
    if not allowed:
        raise PermissionDenied("Le contenu de ce Groupe est privé.")
    limit = max(1, min(int(limit), SOCIAL_QUERY_LIMIT))
    return _base_contributions().filter(group=group, parent__isnull=True)[:limit]


def activity_contributions(*, viewer, activity, limit=30):
    limit = max(1, min(int(limit), SOCIAL_QUERY_LIMIT))
    candidates = _base_contributions().filter(activity=activity, parent__isnull=True)[:SOCIAL_QUERY_LIMIT]
    return [row for row in candidates if can_view_contribution(viewer, row)][:limit]


def contributions_for_profile(*, profile, include_removed=True, limit=60):
    queryset = Contribution.objects.select_related("space", "group", "activity", "occurrence").filter(
        author_profile=profile
    )
    if not include_removed:
        queryset = queryset.filter(status=ContributionStatus.PUBLISHED)
    return queryset[: max(1, min(int(limit), SOCIAL_QUERY_LIMIT))]

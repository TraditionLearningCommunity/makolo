from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta

from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from discovery.recommendations import activity_destination, build_activity_recommendations
from groups.models import GroupMembership, GroupMembershipStatus
from organizations.models import OrganizationFollow

from .models import Contribution, ContributionKind, ContributionStatus
from .services import can_view_contribution


STREAM_SOURCE_LIMIT = 40
STREAM_PAGE_SIZE_MAX = 40
STREAM_WINDOW_DAYS = 90


@dataclass(frozen=True)
class ActionStreamItem:
    key: str
    kind: str
    occurred_at: object
    title: str
    summary: str
    activity: object = None
    contribution: object = None
    reasons: tuple[str, ...] = ()
    cta_label: str = ""
    cta_url: str = ""


@dataclass(frozen=True)
class ActionStreamPage:
    items: tuple[ActionStreamItem, ...]
    offset: int
    limit: int
    has_more: bool


def build_action_stream(profile, *, offset=0, limit=20, at=None):
    if not getattr(profile, "is_authenticated", False):
        return ActionStreamPage(items=(), offset=0, limit=limit, has_more=False)
    at = at or timezone.now()
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), STREAM_PAGE_SIZE_MAX))
    cutoff = at - timedelta(days=STREAM_WINDOW_DAYS)
    items = {}

    def merge(item):
        existing = items.get(item.key)
        if existing is None:
            items[item.key] = item
            return
        reasons = tuple(dict.fromkeys((*existing.reasons, *item.reasons)))
        items[item.key] = replace(existing, reasons=reasons, occurred_at=max(existing.occurred_at, item.occurred_at))

    followed_ids = list(
        OrganizationFollow.objects.filter(user=profile).values_list("organization_id", flat=True)[:STREAM_SOURCE_LIMIT]
    )
    if followed_ids:
        activities = (
            Activity.objects.filter(
                space_id__in=followed_ids,
                status=ActivityStatus.PUBLISHED,
                visibility=ActivityVisibility.PUBLIC,
                updated_at__gte=cutoff,
            )
            .exclude(space__verification_status="suspended")
            .select_related("space", "event_vertical", "service_details", "transport_service")
            .order_by("-updated_at", "id")[:STREAM_SOURCE_LIMIT]
        )
        for activity in activities:
            cta_label, cta_url = activity_destination(activity)
            merge(ActionStreamItem(
                key=f"activity:{activity.pk}", kind="activity", occurred_at=activity.updated_at,
                title=activity.title, summary=activity.short_description or activity.description[:220],
                activity=activity, reasons=("Espace suivi",), cta_label=cta_label, cta_url=cta_url,
            ))

    group_ids = list(
        GroupMembership.objects.filter(profile=profile, status=GroupMembershipStatus.ACTIVE)
        .values_list("group_id", flat=True)[:STREAM_SOURCE_LIMIT]
    )
    contribution_query = Contribution.objects.filter(
        group_id__in=group_ids,
        status=ContributionStatus.PUBLISHED,
        parent__isnull=True,
        created_at__gte=cutoff,
    ).select_related("author_profile", "space", "group", "activity", "occurrence").order_by("-created_at", "id")
    for contribution in contribution_query[:STREAM_SOURCE_LIMIT]:
        if not can_view_contribution(profile, contribution):
            continue
        if contribution.activity_id:
            cta_label, cta_url = activity_destination(contribution.activity)
            key = f"activity:{contribution.activity_id}" if contribution.kind == ContributionKind.SHARE else f"contribution:{contribution.pk}"
        else:
            cta_label, cta_url = "Voir le Groupe", ""
            key = f"contribution:{contribution.pk}"
        merge(ActionStreamItem(
            key=key, kind="contribution", occurred_at=contribution.created_at,
            title=contribution.activity.title if contribution.activity_id else contribution.get_kind_display(),
            summary=contribution.body, activity=contribution.activity, contribution=contribution,
            reasons=("Votre Groupe",), cta_label=cta_label, cta_url=cta_url,
        ))

    for recommendation in build_activity_recommendations(profile, limit=STREAM_SOURCE_LIMIT):
        merge(ActionStreamItem(
            key=f"activity:{recommendation.activity.pk}", kind="recommendation",
            occurred_at=recommendation.activity.updated_at, title=recommendation.activity.title,
            summary=recommendation.activity.short_description or recommendation.activity.description[:220],
            activity=recommendation.activity,
            reasons=tuple(reason.label for reason in recommendation.reasons),
            cta_label=recommendation.cta_label, cta_url=recommendation.cta_url,
        ))

    ordered = sorted(items.values(), key=lambda item: (item.occurred_at, item.key), reverse=True)
    window = ordered[offset: offset + limit + 1]
    return ActionStreamPage(items=tuple(window[:limit]), offset=offset, limit=limit, has_more=len(window) > limit)

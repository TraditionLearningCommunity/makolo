from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from groups.models import GroupMembership, GroupMembershipStatus
from journeys.models import Journey, JourneyStatus
from organizations.models import OrganizationFollow

from .models import ActivityBookmark


CANDIDATE_LIMIT_PER_SOURCE = 30
RECOMMENDATION_LIMIT_MAX = 50
SOURCE_DIVERSITY_CAP = 3


@dataclass(frozen=True)
class RecommendationReason:
    code: str
    label: str


@dataclass(frozen=True)
class RecommendationResult:
    activity: Activity
    reasons: tuple[RecommendationReason, ...]
    score: int
    vertical: str
    cta_label: str
    cta_url: str


REASON_LABELS = {
    "following_space": "Parce que vous suivez cet Espace",
    "group_relevance": "Partagée dans l'un de vos Groupes",
    "bookmarked_similar_activity": "Similaire à une Activity enregistrée",
    "past_activity_interest": "Basé sur votre historique d'actions",
}
REASON_WEIGHTS = {
    "following_space": 50,
    "group_relevance": 45,
    "bookmarked_similar_activity": 25,
    "past_activity_interest": 20,
}


def _related(activity, name):
    try:
        return getattr(activity, name)
    except ObjectDoesNotExist:
        return None


def activity_vertical(activity):
    if _related(activity, "event_vertical") is not None:
        return "event"
    if _related(activity, "service_details") is not None:
        return "service"
    if _related(activity, "transport_service") is not None:
        return "transport"
    return "activity"


def activity_destination(activity):
    event = _related(activity, "event_vertical")
    if event is not None:
        return "Voir", reverse("events:detail", kwargs={"slug": event.slug})
    service = _related(activity, "service_details")
    if service is not None:
        return "Commencer", reverse("services:start", kwargs={"pk": service.pk})
    transport = _related(activity, "transport_service")
    if transport is not None:
        departure = (
            activity.occurrences.filter(transport_departure__isnull=False)
            .select_related("transport_departure")
            .order_by("start_at", "id")
            .first()
        )
        if departure is not None:
            return "Voir", reverse("transport:departure-detail", kwargs={"pk": departure.transport_departure.pk})
        return "Voir", reverse("transport:search")
    query = urlencode({"q": activity.title})
    return "Voir", f"{reverse('discovery:home')}?{query}"


def _visible_activity_queryset():
    return (
        Activity.objects.filter(status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
        .exclude(space__verification_status="suspended")
        .select_related("space", "event_vertical", "service_details", "transport_service")
        .order_by("-updated_at", "id")
    )


def build_activity_recommendations(profile, *, limit=12):
    """Bounded, deterministic and explainable Activity-first recommendations.

    Private facts only select coarse privacy-safe reason codes. Followers, likes,
    views and content volume never participate in ranking.
    """
    if not getattr(profile, "is_authenticated", False):
        return []
    limit = max(1, min(int(limit), RECOMMENDATION_LIMIT_MAX))
    candidates = {}

    def add(rows, reason_code):
        for activity in rows:
            row = candidates.setdefault(activity.pk, {"activity": activity, "reasons": set()})
            row["reasons"].add(reason_code)

    followed_space_ids = list(
        OrganizationFollow.objects.filter(user=profile).values_list("organization_id", flat=True)[:CANDIDATE_LIMIT_PER_SOURCE]
    )
    if followed_space_ids:
        add(_visible_activity_queryset().filter(space_id__in=followed_space_ids)[:CANDIDATE_LIMIT_PER_SOURCE], "following_space")

    from social.models import Contribution, ContributionKind, ContributionStatus

    group_ids = list(
        GroupMembership.objects.filter(profile=profile, status=GroupMembershipStatus.ACTIVE)
        .values_list("group_id", flat=True)[:CANDIDATE_LIMIT_PER_SOURCE]
    )
    if group_ids:
        shared_activity_ids = list(
            Contribution.objects.filter(
                group_id__in=group_ids,
                kind=ContributionKind.SHARE,
                status=ContributionStatus.PUBLISHED,
                activity__isnull=False,
            ).values_list("activity_id", flat=True)[:CANDIDATE_LIMIT_PER_SOURCE]
        )
        add(_visible_activity_queryset().filter(pk__in=shared_activity_ids)[:CANDIDATE_LIMIT_PER_SOURCE], "group_relevance")

    bookmarked_ids = list(
        ActivityBookmark.objects.filter(user=profile).values_list("activity_id", flat=True)[:CANDIDATE_LIMIT_PER_SOURCE]
    )
    bookmarked_verticals = set()
    if bookmarked_ids:
        for bookmarked in Activity.objects.filter(pk__in=bookmarked_ids).select_related(
            "event_vertical", "service_details", "transport_service"
        ):
            bookmarked_verticals.add(activity_vertical(bookmarked))

    history_activity_ids = list(
        Journey.objects.filter(beneficiary=profile, status=JourneyStatus.FULFILLED)
        .values_list("activity_id", flat=True).distinct()[:CANDIDATE_LIMIT_PER_SOURCE]
    )
    history_verticals = set()
    if history_activity_ids:
        for past in Activity.objects.filter(pk__in=history_activity_ids).select_related(
            "event_vertical", "service_details", "transport_service"
        ):
            history_verticals.add(activity_vertical(past))

    if bookmarked_verticals or history_verticals:
        excluded = set(bookmarked_ids) | set(history_activity_ids)
        fallback = list(_visible_activity_queryset().exclude(pk__in=excluded)[:CANDIDATE_LIMIT_PER_SOURCE])
        for activity in fallback:
            vertical = activity_vertical(activity)
            if vertical in bookmarked_verticals:
                add([activity], "bookmarked_similar_activity")
            if vertical in history_verticals:
                add([activity], "past_activity_interest")

    ranked = []
    for row in candidates.values():
        activity = row["activity"]
        reasons = tuple(
            RecommendationReason(code=code, label=REASON_LABELS[code])
            for code in sorted(row["reasons"], key=lambda code: (-REASON_WEIGHTS[code], code))
        )
        score = sum(REASON_WEIGHTS[reason.code] for reason in reasons)
        cta_label, cta_url = activity_destination(activity)
        ranked.append(RecommendationResult(
            activity=activity,
            reasons=reasons,
            score=score,
            vertical=activity_vertical(activity),
            cta_label=cta_label,
            cta_url=cta_url,
        ))
    ranked.sort(key=lambda row: (-row.score, -row.activity.updated_at.timestamp(), str(row.activity.pk)))

    selected = []
    per_space = {}
    for row in ranked:
        space_key = row.activity.space_id or f"profile:{row.activity.owner_profile_id}"
        if per_space.get(space_key, 0) >= SOURCE_DIVERSITY_CAP:
            continue
        selected.append(row)
        per_space[space_key] = per_space.get(space_key, 0) + 1
        if len(selected) >= limit:
            break
    return selected

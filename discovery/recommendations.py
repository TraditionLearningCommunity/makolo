from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from core.product_language import vertical_for
from groups.models import GroupMembership, GroupMembershipStatus
from groups.selectors import eligible_activity_ids_for_profile
from journeys.models import Journey, JourneyStatus
from organizations.models import OrganizationFollow
from topics.models import ActivityTopic, ProfileInterest
from transport.selectors import next_public_departure_for_activity, next_public_departures_by_activity

from .candidate_identity import occurrence_candidate_key, service_activity_candidate_key
from .models import ActivityBookmark


CANDIDATE_LIMIT_PER_SOURCE = 30
RECOMMENDATION_LIMIT_MAX = 50
SOURCE_DIVERSITY_CAP = 3
DECLARED_INTEREST_REASON_PREFIX = "declared_interest:"
DECLARED_INTEREST_WEIGHT = 35


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
    candidate_key: str
    cta_label: str
    cta_url: str


REASON_LABELS = {
    "following_space": "Parce que vous suivez cet Espace",
    "group_relevance": "Partagée dans l'un de vos Groupes",
    "bookmarked_similar_activity": "Similaire à une Activity enregistrée",
    "past_activity_interest": "Basé sur votre historique d'actions",
    "capacity_released": "Une capacité vient de se libérer",
    "nearby_now": "Disponible près de votre origine choisie",
    "leave_soon": "Votre prochaine action temporelle approche",
}
# C1 deliberately preserves these deterministic weights as a baseline. They are
# not the future Makolo Discovery ranking doctrine.
REASON_WEIGHTS = {
    "following_space": 50,
    "group_relevance": 45,
    "bookmarked_similar_activity": 25,
    "past_activity_interest": 20,
    "capacity_released": 70,
    "nearby_now": 30,
    "leave_soon": 80,
}


def _reason_weight(code):
    if code.startswith(DECLARED_INTEREST_REASON_PREFIX):
        return DECLARED_INTEREST_WEIGHT
    return REASON_WEIGHTS[code]


def _reason_label(code, interest_labels):
    if code.startswith(DECLARED_INTEREST_REASON_PREFIX):
        topic_code = code[len(DECLARED_INTEREST_REASON_PREFIX):]
        topic_label = interest_labels.get(topic_code, topic_code)
        return f"Parce que {topic_label} fait partie de vos centres d’intérêt."
    return REASON_LABELS[code]


def activity_vertical(activity):
    """Compatibility alias around the canonical vertical resolver."""
    return vertical_for(activity)


def activity_destination(activity, *, transport_departure=None):
    vertical = vertical_for(activity)
    if vertical == "event":
        return "Voir", reverse("events:detail", kwargs={"slug": activity.event_vertical.slug})
    if vertical == "service":
        return "Commencer", reverse("services:start", kwargs={"pk": activity.service_details.pk})
    if vertical == "transport":
        departure = transport_departure or next_public_departure_for_activity(activity)
        if departure is not None:
            return "Voir", reverse("transport:departure-detail", kwargs={"pk": departure.pk})
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


def _next_viable_occurrences(activity_ids, *, now):
    result = {}
    if not activity_ids:
        return result
    occurrences = (
        Occurrence.objects.filter(
            activity_id__in=activity_ids,
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
            status=OccurrenceStatus.SCHEDULED,
            start_at__gt=now,
        )
        .order_by("activity_id", "start_at", "id")
    )
    for occurrence in occurrences:
        result.setdefault(occurrence.activity_id, occurrence)
    return result


def _viability_context(profile, activities, *, now):
    """Resolve explicit viable facts in batches; no actionability score."""
    by_vertical = {"event": [], "transport": [], "service": [], "generic": []}
    for activity in activities:
        by_vertical.setdefault(vertical_for(activity), []).append(activity.pk)

    occurrence_ids = by_vertical.get("event", []) + by_vertical.get("generic", [])
    occurrences = _next_viable_occurrences(occurrence_ids, now=now)
    departures = next_public_departures_by_activity(by_vertical.get("transport", []), now=now)

    viable_ids = set(by_vertical.get("service", []))
    viable_ids.update(occurrences)
    viable_ids.update(departures)
    viable_ids &= eligible_activity_ids_for_profile(profile, viable_ids)
    return viable_ids, occurrences, departures


def _candidate_key(activity, *, occurrence=None, departure=None):
    vertical = vertical_for(activity)
    if vertical == "service":
        return str(service_activity_candidate_key(activity))
    if vertical == "transport" and departure is not None:
        return str(occurrence_candidate_key(departure.occurrence_id))
    if occurrence is not None:
        return str(occurrence_candidate_key(occurrence))
    return f"activity:{activity.pk}"


def build_activity_recommendations(profile, *, limit=12, context=None):
    """Bounded, deterministic and explainable Activity-first baseline.

    Candidate reasons are accumulated by Activity so multiple provenances enrich
    one recommendation rather than creating duplicate cards. Before ranking, C1
    requires a viable vertical-owned possibility and composes Group eligibility.
    """
    if not getattr(profile, "is_authenticated", False):
        return []
    limit = max(1, min(int(limit), RECOMMENDATION_LIMIT_MAX))
    candidates = {}
    interest_labels = {}

    def add(rows, reason_code):
        for activity in rows:
            row = candidates.setdefault(activity.pk, {"activity": activity, "reasons": set()})
            row["reasons"].add(reason_code)

    declared_interests = list(
        ProfileInterest.objects.filter(profile=profile, topic__is_active=True)
        .select_related("topic")
        .order_by("topic__label", "topic__code")[:CANDIDATE_LIMIT_PER_SOURCE]
    )
    if declared_interests:
        topic_ids = [interest.topic_id for interest in declared_interests]
        interest_labels = {interest.topic.code: interest.topic.label for interest in declared_interests}
        matched_topics_by_activity = {}
        topic_links = (
            ActivityTopic.objects.filter(topic_id__in=topic_ids)
            .values_list("activity_id", "topic__code")
            .order_by("created_at", "id")[:CANDIDATE_LIMIT_PER_SOURCE]
        )
        for activity_id, topic_code in topic_links:
            matched_topics_by_activity.setdefault(activity_id, set()).add(topic_code)
        if matched_topics_by_activity:
            for activity in _visible_activity_queryset().filter(pk__in=matched_topics_by_activity):
                topic_code = sorted(matched_topics_by_activity[activity.pk])[0]
                add([activity], f"{DECLARED_INTEREST_REASON_PREFIX}{topic_code}")

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

    from spatiotemporal.opportunities import recommendation_reason_map

    m6_reason_map = recommendation_reason_map(
        profile,
        origin=(context or {}).get("origin"),
        limit=CANDIDATE_LIMIT_PER_SOURCE,
    )
    if m6_reason_map:
        for activity in _visible_activity_queryset().filter(pk__in=m6_reason_map):
            for reason_code in sorted(m6_reason_map[activity.pk]):
                add([activity], reason_code)

    candidate_activities = [row["activity"] for row in candidates.values()]
    now = timezone.now()
    viable_ids, viable_occurrences, valid_departures = _viability_context(
        profile,
        candidate_activities,
        now=now,
    )

    ranked = []
    for row in candidates.values():
        activity = row["activity"]
        if activity.pk not in viable_ids:
            continue
        reasons = tuple(
            RecommendationReason(code=code, label=_reason_label(code, interest_labels))
            for code in sorted(row["reasons"], key=lambda code: (-_reason_weight(code), code))
        )
        score = sum(_reason_weight(reason.code) for reason in reasons)
        departure = valid_departures.get(activity.pk)
        occurrence = viable_occurrences.get(activity.pk)
        cta_label, cta_url = activity_destination(activity, transport_departure=departure)
        ranked.append(RecommendationResult(
            activity=activity,
            reasons=reasons,
            score=score,
            vertical=activity_vertical(activity),
            candidate_key=_candidate_key(activity, occurrence=occurrence, departure=departure),
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

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import Q

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from topics.models import OpenToKind, ProfileInterest

from .models import ActionNeed, ProfileSolicitation


User = get_user_model()


@dataclass(frozen=True)
class ProfileCandidate:
    """Privacy-safe read model for one Profile search result."""

    profile_id: UUID
    display_name: str
    city: str
    country: str
    open_to_label: str
    reasons: tuple[str, ...]


def _eligible_profiles(need: ActionNeed):
    queryset = (
        User.objects.filter(
            is_active=True,
            profile__public_profile=True,
            profile__searchable=True,
            open_to_declarations__kind=need.open_to_kind,
            open_to_declarations__is_active=True,
            open_to_declarations__is_searchable=True,
        )
        .select_related("profile")
        .distinct()
    )
    if need.owner_profile_id:
        queryset = queryset.exclude(pk=need.owner_profile_id)
    return queryset


def profile_is_eligible_for_need(*, need: ActionNeed, profile) -> bool:
    """Absolute discoverability gate used before a solicitation can be sent."""

    return _eligible_profiles(need).filter(pk=getattr(profile, "pk", None)).exists()


def search_profiles_for_need(*, need: ActionNeed, limit: int = 100) -> list[ProfileCandidate]:
    """Find Profiles using only disclosure signals explicitly allowed by G7.

    There is no materialized result table and no human score. OpenTo compatibility
    is an absolute gate. Public interests and public personal Activities only
    contribute explainable reasons and deterministic ordering.
    """

    limit = max(1, min(int(limit or 100), 200))
    profiles = list(_eligible_profiles(need).order_by("username", "id")[:limit])
    if not profiles:
        return []

    profile_ids = [profile.pk for profile in profiles]
    need_topics = list(need.topics.filter(is_active=True).order_by("label", "code"))
    topic_ids = [topic.pk for topic in need_topics]

    interests_by_profile: dict[UUID, list[str]] = {profile_id: [] for profile_id in profile_ids}
    activities_by_profile: dict[UUID, list[str]] = {profile_id: [] for profile_id in profile_ids}

    if topic_ids:
        for interest in (
            ProfileInterest.objects.filter(
                profile_id__in=profile_ids,
                topic_id__in=topic_ids,
                is_public=True,
                topic__is_active=True,
            )
            .select_related("topic")
            .order_by("topic__label", "topic__code", "profile_id")
        ):
            interests_by_profile[interest.profile_id].append(interest.topic.label)

        public_activities = (
            Activity.objects.filter(
                owner_profile_id__in=profile_ids,
                status=ActivityStatus.PUBLISHED,
                visibility=ActivityVisibility.PUBLIC,
                topic_links__topic_id__in=topic_ids,
                topic_links__topic__is_active=True,
            )
            .order_by("owner_profile_id", "title", "id")
            .distinct()
        )
        for activity in public_activities:
            activities_by_profile[activity.owner_profile_id].append(activity.title)

    open_to_label = OpenToKind(need.open_to_kind).label
    candidates = []
    for profile in profiles:
        public_interests = interests_by_profile[profile.pk]
        public_activities = activities_by_profile[profile.pk]
        reasons = [f"Ouverte à : {open_to_label}"]
        reasons.extend(f"Centre d’intérêt public : {label}" for label in public_interests)
        reasons.extend(f"A organisé « {title} »" for title in public_activities[:2])
        candidates.append(
            (
                bool(public_interests),
                bool(public_activities),
                (profile.full_name or profile.username).casefold(),
                str(profile.pk),
                ProfileCandidate(
                    profile_id=profile.pk,
                    display_name=profile.full_name or profile.username,
                    city=profile.profile.city or "",
                    country=profile.profile.country or "",
                    open_to_label=open_to_label,
                    reasons=tuple(reasons),
                ),
            )
        )

    candidates.sort(key=lambda row: (-int(row[0]), -int(row[1]), row[2], row[3]))
    return [row[4] for row in candidates]


def action_needs_for_actor(actor):
    """Return needs the actor may manage without reading legacy memberships."""

    if not getattr(actor, "is_authenticated", False):
        return ActionNeed.objects.none()
    if getattr(actor, "is_superuser", False):
        return ActionNeed.objects.all().select_related("owner_profile", "space", "activity", "opportunity")

    query = Q(owner_profile=actor)
    manageable_spaces = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE)
    manageable_activities = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_MANAGE)

    if manageable_spaces is None or manageable_activities is None:
        return ActionNeed.objects.all().select_related("owner_profile", "space", "activity", "opportunity")
    if manageable_spaces:
        query |= Q(space_id__in=manageable_spaces, activity__isnull=True)
    if manageable_activities:
        query |= Q(activity_id__in=manageable_activities)

    return (
        ActionNeed.objects.filter(query)
        .select_related("owner_profile", "space", "activity", "opportunity")
        .distinct()
    )


def solicitations_for_recipient(profile):
    return (
        ProfileSolicitation.objects.filter(recipient_profile=profile)
        .select_related("need", "need__owner_profile", "need__space", "need__activity", "need__opportunity", "sent_by")
        .prefetch_related("need__topics")
    )

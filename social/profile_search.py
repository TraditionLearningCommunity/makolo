from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from organizations.models import Organization
from topics.models import ActionMatchKind, ProfileInterest, SpaceOpenTo

from .models import ActionNeed, ActionNetworkBlock, ActionProposal, ActionProposalDirection, ActionProposalStatus


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


@dataclass(frozen=True)
class SpaceCandidate:
    """Minimum-disclosure read model for one Space candidate."""

    space_id: UUID
    display_name: str
    city: str
    country: str
    open_to_label: str
    reasons: tuple[str, ...]


def _blocked_profile_ids(need: ActionNeed) -> set[UUID]:
    if need.owner_profile_id:
        outbound = ActionNetworkBlock.objects.filter(blocker_profile_id=need.owner_profile_id).exclude(blocked_profile=None)
        inbound = ActionNetworkBlock.objects.filter(blocked_profile_id=need.owner_profile_id).exclude(blocker_profile=None)
        return set(outbound.values_list("blocked_profile_id", flat=True)) | set(inbound.values_list("blocker_profile_id", flat=True))
    if need.space_id:
        outbound = ActionNetworkBlock.objects.filter(blocker_space_id=need.space_id).exclude(blocked_profile=None)
        inbound = ActionNetworkBlock.objects.filter(blocked_space_id=need.space_id).exclude(blocker_profile=None)
        return set(outbound.values_list("blocked_profile_id", flat=True)) | set(inbound.values_list("blocker_profile_id", flat=True))
    return set()


def _blocked_space_ids(need: ActionNeed) -> set[UUID]:
    if need.owner_profile_id:
        outbound = ActionNetworkBlock.objects.filter(blocker_profile_id=need.owner_profile_id).exclude(blocked_space=None)
        inbound = ActionNetworkBlock.objects.filter(blocked_profile_id=need.owner_profile_id).exclude(blocker_space=None)
        return set(outbound.values_list("blocked_space_id", flat=True)) | set(inbound.values_list("blocker_space_id", flat=True))
    if need.space_id:
        outbound = ActionNetworkBlock.objects.filter(blocker_space_id=need.space_id).exclude(blocked_space=None)
        inbound = ActionNetworkBlock.objects.filter(blocked_space_id=need.space_id).exclude(blocker_space=None)
        return set(outbound.values_list("blocked_space_id", flat=True)) | set(inbound.values_list("blocker_space_id", flat=True))
    return set()


def _eligible_profiles(need: ActionNeed):
    queryset = (
        User.objects.filter(
            is_active=True,
            profile__searchable=True,
            open_to_declarations__kind=need.match_kind,
            open_to_declarations__is_active=True,
            open_to_declarations__is_searchable=True,
        )
        .select_related("profile")
        .distinct()
    )
    if need.owner_profile_id:
        queryset = queryset.exclude(pk=need.owner_profile_id)
    blocked = _blocked_profile_ids(need)
    if blocked:
        queryset = queryset.exclude(pk__in=blocked)
    return queryset


def _eligible_spaces(need: ActionNeed):
    queryset = (
        Organization.objects.filter(
            open_to_declarations__kind=need.match_kind,
            open_to_declarations__is_active=True,
            open_to_declarations__is_searchable=True,
        )
        .distinct()
    )
    if need.space_id:
        queryset = queryset.exclude(pk=need.space_id)
    blocked = _blocked_space_ids(need)
    if blocked:
        queryset = queryset.exclude(pk__in=blocked)
    return queryset


def profile_is_eligible_for_need(*, need: ActionNeed, profile) -> bool:
    if need.candidate_kind == "space":
        return False
    return _eligible_profiles(need).filter(pk=getattr(profile, "pk", None)).exists()


def space_is_eligible_for_need(*, need: ActionNeed, space) -> bool:
    if need.candidate_kind == "profile":
        return False
    return _eligible_spaces(need).filter(pk=getattr(space, "pk", None)).exists()


def search_profiles_for_need(*, need: ActionNeed, limit: int = 100) -> list[ProfileCandidate]:
    """Find Profiles from explicit searchable signals without exposing private facts."""

    if need.candidate_kind == "space":
        return []
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

    open_to_label = ActionMatchKind(need.match_kind).label
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


def search_spaces_for_need(*, need: ActionNeed, limit: int = 100) -> list[SpaceCandidate]:
    if need.candidate_kind == "profile":
        return []
    limit = max(1, min(int(limit or 100), 200))
    spaces = list(_eligible_spaces(need).order_by("name", "id")[:limit])
    if not spaces:
        return []
    topic_ids = list(need.topics.filter(is_active=True).values_list("id", flat=True))
    open_to_label = ActionMatchKind(need.match_kind).label
    topic_labels_by_space: dict[UUID, list[str]] = {space.pk: [] for space in spaces}
    if topic_ids:
        for declaration in (
            SpaceOpenTo.objects.filter(
                space_id__in=[space.pk for space in spaces],
                kind=need.match_kind,
                is_active=True,
                is_searchable=True,
                topic_id__in=topic_ids,
            )
            .select_related("topic")
            .order_by("topic__label", "space_id")
        ):
            topic_labels_by_space[declaration.space_id].append(declaration.topic.label)

    candidates = []
    for space in spaces:
        topic_labels = topic_labels_by_space[space.pk]
        reasons = [f"Ouvert à : {open_to_label}"]
        reasons.extend(f"Topic compatible : {label}" for label in topic_labels)
        candidates.append(
            (
                bool(topic_labels),
                space.name.casefold(),
                str(space.pk),
                SpaceCandidate(
                    space_id=space.pk,
                    display_name=space.name,
                    city=space.city or "",
                    country=space.country or "",
                    open_to_label=open_to_label,
                    reasons=tuple(reasons),
                ),
            )
        )
    candidates.sort(key=lambda row: (-int(row[0]), row[1], row[2]))
    return [row[3] for row in candidates]


def action_needs_for_actor(actor):
    """Return Needs the actor may manage through fine Action Network authority."""

    if not getattr(actor, "is_authenticated", False):
        return ActionNeed.objects.none()
    if getattr(actor, "is_superuser", False):
        return ActionNeed.objects.all().select_related("owner_profile", "space", "activity", "occurrence", "opportunity")

    query = Q(owner_profile=actor)
    manageable_spaces = space_ids_with_permission(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE)
    manageable_activities = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_ACTION_NETWORK_MANAGE)

    if manageable_spaces is None or manageable_activities is None:
        return ActionNeed.objects.all().select_related("owner_profile", "space", "activity", "occurrence", "opportunity")
    if manageable_spaces:
        query |= Q(space_id__in=manageable_spaces)
    if manageable_activities:
        query |= Q(activity_id__in=manageable_activities)

    return (
        ActionNeed.objects.filter(query)
        .select_related("owner_profile", "space", "activity", "occurrence", "opportunity")
        .distinct()
    )


def action_proposals_requiring_actor_response(actor, *, at=None):
    """Canonical Action Inbox: pending, unexpired Proposals the actor may currently answer."""

    if not getattr(actor, "is_authenticated", False):
        return ActionProposal.objects.none()
    at = at or timezone.now()
    live = Q(status=ActionProposalStatus.PENDING) & (Q(expires_at__isnull=True) | Q(expires_at__gt=at))
    if getattr(actor, "is_superuser", False):
        return ActionProposal.objects.filter(live).select_related(
            "candidate_profile", "candidate_space", "initiated_by", "need", "need__owner_profile", "need__space",
            "need__activity", "need__occurrence", "need__opportunity"
        ).prefetch_related("need__topics")

    query = Q(
        direction=ActionProposalDirection.OWNER_TO_CANDIDATE,
        candidate_profile=actor,
    )

    manageable_space_ids = space_ids_with_permission(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE)
    manageable_activity_ids = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_ACTION_NETWORK_MANAGE)

    if manageable_space_ids is None:
        query |= Q(direction=ActionProposalDirection.OWNER_TO_CANDIDATE, candidate_space__isnull=False)
    elif manageable_space_ids:
        query |= Q(direction=ActionProposalDirection.OWNER_TO_CANDIDATE, candidate_space_id__in=manageable_space_ids)

    owner_query = Q(direction=ActionProposalDirection.CANDIDATE_TO_OWNER, need__owner_profile=actor)
    if manageable_space_ids is None or manageable_activity_ids is None:
        owner_query |= Q(direction=ActionProposalDirection.CANDIDATE_TO_OWNER, need__space__isnull=False)
    else:
        if manageable_space_ids:
            owner_query |= Q(
                direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
                need__space_id__in=manageable_space_ids,
            )
        if manageable_activity_ids:
            owner_query |= Q(
                direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
                need__activity_id__in=manageable_activity_ids,
            )
    query |= owner_query

    return (
        ActionProposal.objects.filter(query).filter(live)
        .select_related(
            "candidate_profile", "candidate_space", "initiated_by", "need", "need__owner_profile", "need__space",
            "need__activity", "need__occurrence", "need__opportunity"
        )
        .prefetch_related("need__topics")
        .distinct()
    )


def proposals_for_profile(profile):
    """Compatibility selector retained for callers that only need Profile-targeted proposals."""

    return (
        ActionProposal.objects.filter(candidate_profile=profile, direction=ActionProposalDirection.OWNER_TO_CANDIDATE)
        .select_related("need", "need__owner_profile", "need__space", "need__activity", "need__occurrence", "need__opportunity", "initiated_by")
        .prefetch_related("need__topics")
    )


# Compatibility selector name for the pre-convergence UI.
solicitations_for_recipient = proposals_for_profile
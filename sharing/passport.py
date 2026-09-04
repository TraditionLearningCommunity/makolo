from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from organizations.permissions import organization_has_public_profile
from topics.models import ProfileInterest, ProfileOpenTo, Topic
from topics.services import public_profile_interests, public_profile_open_to
from trust.credential_models import CredentialStatus, CredentialType
from trust.credential_selectors import credentials_for_profile, credentials_issued_by_space
from trust.models import ProofStatus
from trust.selectors import active_public_verifications_for_space, proofs_for_profile


PASSPORT_PUBLIC = "public"
PASSPORT_COMPLETE = "complete"
PASSPORT_THEMATIC = "thematic"
PASSPORT_CUSTOM = "custom"
PASSPORT_VARIANTS = (
    PASSPORT_PUBLIC,
    PASSPORT_COMPLETE,
    PASSPORT_THEMATIC,
    PASSPORT_CUSTOM,
)
PASSPORT_VARIANT_LABELS = {
    PASSPORT_PUBLIC: "Public",
    PASSPORT_COMPLETE: "Complet",
    PASSPORT_THEMATIC: "Thématique",
    PASSPORT_CUSTOM: "Personnalisé",
}

# A Passport describes facts that reached an externally meaningful Activity state.
# Drafts are intentionally excluded, including from the owner's complete Passport.
PASSPORT_ACTIVITY_STATUSES = (
    ActivityStatus.PUBLISHED,
    ActivityStatus.COMPLETED,
    ActivityStatus.ARCHIVED,
)


@dataclass(frozen=True)
class PassportProjection:
    """Read model only. It never becomes a second source of truth."""

    subject_kind: str
    subject: object
    variant: str
    generated_at: object
    identity: dict
    interests: tuple = ()
    open_to: tuple = ()
    activities: tuple = ()
    proofs: tuple = ()
    credentials: tuple = ()
    trust_verifications: tuple = ()
    credential_summary: tuple = ()
    topics: tuple = ()

    @property
    def variant_label(self):
        return PASSPORT_VARIANT_LABELS[self.variant]


class PassportSelectionError(PermissionDenied):
    pass


def profile_has_public_passport(profile) -> bool:
    return UserProfile.objects.filter(user=profile, public_profile=True).exists()


def space_has_public_passport(space) -> bool:
    return organization_has_public_profile(space)


def _avatar_url(profile):
    if not getattr(profile, "avatar", None):
        return ""
    try:
        return profile.avatar.url
    except ValueError:
        return ""


def _profile_identity(profile):
    profile_row = UserProfile.objects.filter(user=profile).first()
    location_parts = []
    if profile_row:
        location_parts = [part for part in (profile_row.city, profile_row.country) if part]
    links = tuple(
        (label, value)
        for label, value in (
            ("Site web", profile.website),
            ("LinkedIn", profile.linkedin_url),
            ("Facebook", profile.facebook_url),
            ("Instagram", profile.instagram_url),
            ("TikTok", profile.tiktok_url),
            ("X / Twitter", profile.x_url),
            ("YouTube", profile.youtube_url),
        )
        if value
    )
    return {
        "name": profile.full_name or profile.username,
        "avatar_url": _avatar_url(profile),
        "bio": profile.bio or "",
        "profession": profile_row.profession if profile_row and profile_row.profession else "",
        "location": ", ".join(location_parts),
        "links": links,
    }


def _space_identity(space):
    return {
        "name": space.name,
        "avatar_url": "",
        "bio": space.description or "",
        "profession": "",
        "location": ", ".join(part for part in (space.city, space.country) if part),
        "links": (("Site web", space.website),) if space.website else (),
    }


def _topics_from_codes(topic_codes):
    normalized = tuple(dict.fromkeys(code.strip() for code in (topic_codes or ()) if code and code.strip()))
    if not normalized:
        return ()
    return tuple(Topic.objects.filter(code__in=normalized, is_active=True).order_by("label", "code"))


def _validate_selection(queryset, selected_ids, *, label):
    if selected_ids is None:
        return queryset
    requested = {str(value).strip() for value in selected_ids if str(value).strip()}
    if not requested:
        return queryset.none()
    allowed = {str(value) for value in queryset.values_list("pk", flat=True)}
    if not requested.issubset(allowed):
        raise PassportSelectionError(f"Sélection Passeport non autorisée : {label}.")
    return queryset.filter(pk__in=requested)


def _filter_activity_topics(queryset, topics, *, thematic):
    if not thematic:
        return queryset
    if not topics:
        return queryset.none()
    return queryset.filter(topic_links__topic__in=topics).distinct()


def _profile_activity_queryset(profile, *, public_only):
    queryset = Activity.objects.filter(
        owner_profile=profile,
        status__in=PASSPORT_ACTIVITY_STATUSES,
    )
    if public_only:
        queryset = queryset.filter(visibility=ActivityVisibility.PUBLIC)
    return queryset.order_by("title", "id")


def _profile_proof_queryset(profile, *, public_only):
    queryset = proofs_for_profile(profile).filter(status=ProofStatus.ACTIVE)
    if public_only:
        queryset = queryset.filter(
            is_public=True,
            journey__activity__visibility=ActivityVisibility.PUBLIC,
            journey__activity__status__in=PASSPORT_ACTIVITY_STATUSES,
        )
    return queryset


def _profile_credential_queryset(profile, *, public_only):
    queryset = credentials_for_profile(profile, valid_only=public_only)
    if public_only:
        queryset = queryset.filter(
            activity__visibility=ActivityVisibility.PUBLIC,
            activity__status__in=PASSPORT_ACTIVITY_STATUSES,
        )
    return queryset


def build_profile_passport(
    profile,
    *,
    variant=PASSPORT_PUBLIC,
    topic_codes=(),
    selected_activity_ids=None,
    selected_proof_ids=None,
    selected_credential_ids=None,
    selected_sections=None,
):
    if variant not in PASSPORT_VARIANTS:
        raise ValueError("Variante Passeport inconnue.")

    public_only = variant == PASSPORT_PUBLIC
    thematic = variant == PASSPORT_THEMATIC
    custom = variant == PASSPORT_CUSTOM
    topics = _topics_from_codes(topic_codes) if thematic else ()

    if public_only:
        interests_qs = public_profile_interests(profile=profile)
        open_to_qs = public_profile_open_to(profile=profile)
    else:
        interests_qs = ProfileInterest.objects.filter(
            profile=profile,
            topic__is_active=True,
        ).select_related("topic").order_by("topic__label", "topic__code")
        open_to_qs = ProfileOpenTo.objects.filter(
            profile=profile,
            is_active=True,
        ).select_related("topic").order_by("kind", "topic__label")

    activities_qs = _profile_activity_queryset(profile, public_only=public_only)
    proofs_qs = _profile_proof_queryset(profile, public_only=public_only)
    credentials_qs = _profile_credential_queryset(profile, public_only=public_only)

    if thematic:
        topic_ids = [topic.pk for topic in topics]
        if topic_ids:
            interests_qs = interests_qs.filter(topic_id__in=topic_ids)
            open_to_qs = open_to_qs.filter(topic_id__in=topic_ids)
            activities_qs = _filter_activity_topics(activities_qs, topics, thematic=True)
            proofs_qs = proofs_qs.filter(journey__activity__topic_links__topic__in=topics).distinct()
            credentials_qs = credentials_qs.filter(activity__topic_links__topic__in=topics).distinct()
        else:
            interests_qs = interests_qs.none()
            open_to_qs = open_to_qs.none()
            activities_qs = activities_qs.none()
            proofs_qs = proofs_qs.none()
            credentials_qs = credentials_qs.none()

    if custom:
        activities_qs = _validate_selection(
            activities_qs,
            selected_activity_ids or (),
            label="Activities",
        )
        proofs_qs = _validate_selection(
            proofs_qs,
            selected_proof_ids or (),
            label="Proofs",
        )
        credentials_qs = _validate_selection(
            credentials_qs,
            selected_credential_ids or (),
            label="Credentials",
        )
        sections = set(selected_sections or ())
        if "interests" not in sections:
            interests_qs = interests_qs.none()
        if "open_to" not in sections:
            open_to_qs = open_to_qs.none()
    else:
        sections = {"identity", "bio", "links", "interests", "open_to"}

    identity = _profile_identity(profile)
    if custom:
        if "bio" not in sections:
            identity["bio"] = ""
        if "links" not in sections:
            identity["links"] = ()
        if "location" not in sections:
            identity["location"] = ""
        if "profession" not in sections:
            identity["profession"] = ""

    return PassportProjection(
        subject_kind="profile",
        subject=profile,
        variant=variant,
        generated_at=timezone.now(),
        identity=identity,
        interests=tuple(interests_qs),
        open_to=tuple(open_to_qs),
        activities=tuple(activities_qs),
        proofs=tuple(proofs_qs),
        credentials=tuple(credentials_qs),
        topics=topics,
    )


def _space_activity_queryset(space, *, public_only):
    queryset = Activity.objects.filter(
        space=space,
        status__in=PASSPORT_ACTIVITY_STATUSES,
    )
    if public_only:
        queryset = queryset.filter(visibility=ActivityVisibility.PUBLIC)
    return queryset.order_by("title", "id")


def _space_credential_summary(credentials_qs):
    labels = dict(CredentialType.choices)
    rows = credentials_qs.values("credential_type").annotate(count=Count("id")).order_by("credential_type")
    return tuple(
        {
            "credential_type": row["credential_type"],
            "label": labels.get(row["credential_type"], row["credential_type"]),
            "count": row["count"],
        }
        for row in rows
    )


def build_space_passport(
    space,
    *,
    variant=PASSPORT_PUBLIC,
    topic_codes=(),
    selected_activity_ids=None,
    selected_credential_ids=None,
    selected_sections=None,
):
    if variant not in PASSPORT_VARIANTS:
        raise ValueError("Variante Passeport inconnue.")

    public_only = variant == PASSPORT_PUBLIC
    thematic = variant == PASSPORT_THEMATIC
    custom = variant == PASSPORT_CUSTOM
    topics = _topics_from_codes(topic_codes) if thematic else ()

    activities_qs = _space_activity_queryset(space, public_only=public_only)
    credentials_qs = credentials_issued_by_space(space, valid_only=True).filter(
        activity__status__in=PASSPORT_ACTIVITY_STATUSES,
    )
    if public_only:
        credentials_qs = credentials_qs.filter(activity__visibility=ActivityVisibility.PUBLIC)

    if thematic:
        if topics:
            activities_qs = _filter_activity_topics(activities_qs, topics, thematic=True)
            credentials_qs = credentials_qs.filter(activity__topic_links__topic__in=topics).distinct()
        else:
            activities_qs = activities_qs.none()
            credentials_qs = credentials_qs.none()

    if custom:
        activities_qs = _validate_selection(
            activities_qs,
            selected_activity_ids or (),
            label="Activities",
        )
        if selected_credential_ids:
            credentials_qs = _validate_selection(
                credentials_qs,
                selected_credential_ids,
                label="Credentials",
            )
        sections = set(selected_sections or ())
    else:
        sections = {"identity", "bio", "links", "location", "trust", "credentials"}

    identity = _space_identity(space)
    if custom:
        if "bio" not in sections:
            identity["bio"] = ""
        if "links" not in sections:
            identity["links"] = ()
        if "location" not in sections:
            identity["location"] = ""

    trust_verifications = ()
    if not custom or "trust" in sections:
        trust_verifications = tuple(active_public_verifications_for_space(space))

    credential_summary = ()
    if not custom or "credentials" in sections or selected_credential_ids:
        credential_summary = _space_credential_summary(credentials_qs)

    return PassportProjection(
        subject_kind="space",
        subject=space,
        variant=variant,
        generated_at=timezone.now(),
        identity=identity,
        activities=tuple(activities_qs),
        trust_verifications=trust_verifications,
        credential_summary=credential_summary,
        topics=topics,
    )


def profile_passport_topic_options(profile):
    activity_ids = set(
        _profile_activity_queryset(profile, public_only=False).values_list("pk", flat=True)
    )
    activity_ids.update(
        credentials_for_profile(profile).values_list("activity_id", flat=True)
    )
    activity_ids.update(
        proofs_for_profile(profile).values_list("journey__activity_id", flat=True)
    )
    topic_ids = set(
        ProfileInterest.objects.filter(profile=profile, topic__is_active=True).values_list("topic_id", flat=True)
    )
    topic_ids.update(
        Topic.objects.filter(activity_links__activity_id__in=activity_ids).values_list("pk", flat=True)
    )
    return Topic.objects.filter(pk__in=topic_ids, is_active=True).order_by("label", "code")


def space_passport_topic_options(space):
    return Topic.objects.filter(
        is_active=True,
        activity_links__activity__space=space,
        activity_links__activity__status__in=PASSPORT_ACTIVITY_STATUSES,
    ).distinct().order_by("label", "code")

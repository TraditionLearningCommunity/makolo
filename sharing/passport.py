from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import GenderCode, UserProfile
from accounts.profile_visibility import ProfileVisibilityResolver
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.models import AuthorityScope, Mandate, MandateStatus
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.permissions import organization_has_public_profile
from topics.models import ProfileInterest, ProfileOpenTo, Topic
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
    activity_involvements: tuple = ()
    trust_verifications: tuple = ()
    credential_summary: tuple = ()
    # Owner-only context; membership never implies authority.
    team_affiliations: tuple = ()
    group_affiliations: tuple = ()
    authorized_space_affiliations: tuple = ()
    active_space_mandates: tuple = ()
    # Internal Space teams require a separate team-management permission.
    space_teams: tuple = ()
    topics: tuple = ()

    @property
    def variant_label(self):
        return PASSPORT_VARIANT_LABELS[self.variant]

    @property
    def has_content(self):
        identity = self.identity or {}
        return bool(
            identity.get("name")
            or identity.get("bio")
            or identity.get("headline")
            or identity.get("location")
            or identity.get("links")
            or self.interests
            or self.open_to
            or self.activities
            or self.proofs
            or self.credentials
            or self.activity_involvements
            or self.trust_verifications
            or self.credential_summary
            or self.team_affiliations
            or self.group_affiliations
            or self.authorized_space_affiliations
            or self.active_space_mandates
            or self.space_teams
        )


class PassportSelectionError(PermissionDenied):
    pass


def profile_has_public_passport(profile) -> bool:
    return UserProfile.objects.filter(
        user=profile,
        public_profile=True,
    ).exists()


def space_has_public_passport(space) -> bool:
    return bool(organization_has_public_profile(space))


def _avatar_url(profile):
    if getattr(profile, "avatar", None):
        try:
            return profile.avatar.url
        except ValueError:
            pass
    metadata = profile.metadata if isinstance(profile.metadata, dict) else {}
    return str(metadata.get("avatar_url") or "")


def _profile_identity(profile):
    from sharing.models import PublicIdentifier

    public_identifier = (
        PublicIdentifier.objects.filter(profile=profile)
        .values_list("identifier", flat=True).first()
    ) or profile.username
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
        "identifier": public_identifier,
        "avatar_url": _avatar_url(profile),
        "bio": profile.bio or "",
        "profession": profile_row.profession if profile_row and profile_row.profession else "",
        "headline": profile_row.profession if profile_row and profile_row.profession else "",
        "company_name": profile_row.company_name or "" if profile_row else "",
        "organization_name": profile_row.organization_name or "" if profile_row else "",
        "location": ", ".join(location_parts),
        "links": links,
    }


def _space_identity(space):
    headline = "Organisation" if space.archetype == "generic" else space.get_archetype_display()
    return {
        "name": space.name,
        "avatar_url": "",
        "bio": space.description or "",
        "profession": "",
        "headline": headline,
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
    return queryset.prefetch_related("topic_links__topic").order_by("title", "id")


def _profile_proof_queryset(profile, *, public_only):
    queryset = proofs_for_profile(profile).filter(status=ProofStatus.ACTIVE)
    if public_only:
        queryset = queryset.filter(
            is_public=True,
            journey__activity__visibility=ActivityVisibility.PUBLIC,
            journey__activity__status__in=PASSPORT_ACTIVITY_STATUSES,
        )
    return queryset.select_related("journey__activity").prefetch_related(
        "journey__activity__topic_links__topic",
    )


def _profile_credential_queryset(profile, *, public_only):
    queryset = credentials_for_profile(profile, valid_only=public_only)
    if public_only:
        queryset = queryset.filter(
            activity__visibility=ActivityVisibility.PUBLIC,
            activity__status__in=PASSPORT_ACTIVITY_STATUSES,
        )
    return queryset.select_related("activity").prefetch_related(
        "activity__topic_links__topic",
    )



def _profile_confirmed_involvements(profile, *, public_only=False):
    """Represent contextual, confirmed roles; never infer participation from a booking."""
    from activities.involvement_models import (
        ActivityInvolvement, ActivityInvolvementStatus,
        ActivityInvolvementVisibility, ActivityInvolvementConfirmationBasis,
    )

    rows = ActivityInvolvement.objects.filter(
        profile=profile,
        status=ActivityInvolvementStatus.ACTIVE,
        confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
        activity__status__in=PASSPORT_ACTIVITY_STATUSES,
    )
    if public_only:
        rows = rows.filter(
            visibility=ActivityInvolvementVisibility.PUBLIC,
            activity__visibility=ActivityVisibility.PUBLIC,
        )
    rows = rows.select_related("activity", "occurrence").prefetch_related(
        "functions", "activity__topic_links__topic",
    ).order_by("activity__title", "id")
    return tuple({
        "id": str(row.pk),
        "activity_id": str(row.activity_id),
        "title": row.activity.title,
        "role": " · ".join(
            function.label or function.get_kind_display()
            for function in row.functions.all()
        ) or row.contextual_title,
        "date": (
            row.occurrence.start_date.isoformat()
            if row.occurrence_id and row.occurrence.start_date else ""
        ),
        "topic_codes": [
            link.topic.code for link in row.activity.topic_links.all()
        ],
        "visibility": row.visibility,
    } for row in rows)


def _profile_team_affiliations(profile):
    """Owner-scoped existing memberships, not roles or public endorsements."""
    memberships = (
        TeamMembership.objects.filter(
            user=profile,
            status=TeamMembershipStatus.ACTIVE,
            team__is_active=True,
        )
        .select_related("team__organization")
        .order_by("team__organization__name", "team__name", "id")
    )
    return tuple(
        {"team": row.team.name, "space": row.team.organization.name}
        for row in memberships
    )


def _profile_group_affiliations(profile):
    """Personal group relations; permissions alone never count as membership."""
    from groups.models import GroupMembershipStatus, GroupStatus
    from groups.selectors import groups_for_profile

    # The complete Passport represents current affiliations. Archived groups
    # remain available to their owning domain, not as active membership.
    rows = groups_for_profile(profile).filter(status=GroupStatus.ACTIVE).filter(
        Q(owner_profile=profile)
        | Q(memberships__profile=profile,
            memberships__status=GroupMembershipStatus.ACTIVE)
    ).distinct().order_by("name", "id")
    return tuple({"name": row.name, "slug": row.slug} for row in rows)


def _profile_authorized_space_affiliations(profile):
    """Reuse Moi Spaces without folding in Platform's global superuser reach."""
    from organizations.console_context import authorized_spaces

    spaces = authorized_spaces(profile)
    if profile.is_superuser:
        from authorization.selectors import current_mandates

        mandates = current_mandates().filter(profile=profile)
        ids = set(mandates.filter(
            scope_type=AuthorityScope.SPACE, space__isnull=False
        ).values_list("space_id", flat=True))
        ids.update(mandates.filter(
            scope_type=AuthorityScope.ACTIVITY,
            activity__space__isnull=False,
        ).values_list("activity__space_id", flat=True))
        spaces = spaces.filter(pk__in=ids)
    return tuple(
        {"name": row.name, "slug": row.slug}
        for row in spaces.order_by("name", "id")
    )


def _profile_active_space_mandates(profile, *, at):
    """Current space-scoped authority, distinct from team membership."""
    mandates = (
        Mandate.objects.filter(
            profile=profile,
            scope_type=AuthorityScope.SPACE,
            status=MandateStatus.ACTIVE,
            revoked_at__isnull=True,
            role__is_active=True,
            space__isnull=False,
        )
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
        .select_related("space", "role")
        .order_by("space__name", "role__name", "id")
    )
    return tuple(
        {"role": row.role.name, "space": row.space.name}
        for row in mandates
    )


def build_profile_passport(
    profile,
    *,
    variant=PASSPORT_PUBLIC,
    topic_codes=(),
    selected_activity_ids=None,
    selected_proof_ids=None,
    selected_credential_ids=None,
    selected_sections=None,
    excluded_activity_ids=(),
    excluded_proof_ids=(),
    excluded_credential_ids=(),
    excluded_sections=(),
    viewer=None,
):
    if variant not in PASSPORT_VARIANTS:
        raise ValueError("Variante Passeport inconnue.")

    public_only = variant in (PASSPORT_PUBLIC, PASSPORT_THEMATIC, PASSPORT_CUSTOM)
    thematic = variant == PASSPORT_THEMATIC
    custom = variant == PASSPORT_CUSTOM
    topics = _topics_from_codes(topic_codes) if thematic else ()

    interests_qs = ProfileInterest.objects.filter(
        profile=profile, topic__is_active=True,
    ).select_related("topic").order_by("topic__label", "topic__code")
    open_to_qs = ProfileOpenTo.objects.filter(
        profile=profile, is_active=True,
    ).select_related("topic").order_by("kind", "topic__label")

    # The public variant is always a bounded presentation, even when its
    # owner previews it. A separate authenticated viewer may receive facts
    # explicitly disclosed to their selected audiences.
    effective_viewer = viewer if (
        public_only and getattr(viewer, "is_authenticated", False)
        and viewer.pk != profile.pk
    ) else None
    visibility = ProfileVisibilityResolver(owner=profile, viewer=effective_viewer) if public_only else None

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
        public_sections = {
            "identity", "avatar", "bio", "profession", "company_name",
            "organization_name", "location", "links", "interests",
            "open_to", "activity_involvements",
        }
        using_exclusions = bool(
            excluded_activity_ids or excluded_proof_ids
            or excluded_credential_ids or excluded_sections
        )
        if using_exclusions:
            excluded = set(excluded_sections or ())
            if not excluded.issubset(public_sections - {"identity"}):
                raise PassportSelectionError("Rubrique de Passeport inconnue.")
            for queryset, ids, label in (
                (activities_qs, excluded_activity_ids, "Activities"),
                (proofs_qs, excluded_proof_ids, "Proofs"),
                (credentials_qs, excluded_credential_ids, "Credentials"),
            ):
                if ids:
                    _validate_selection(queryset, ids, label=label)
            activities_qs = activities_qs.exclude(
                pk__in=excluded_activity_ids or (),
            )
            proofs_qs = proofs_qs.exclude(pk__in=excluded_proof_ids or ())
            credentials_qs = credentials_qs.exclude(
                pk__in=excluded_credential_ids or (),
            )
            sections = public_sections - excluded
        elif selected_sections or selected_activity_ids or selected_proof_ids or selected_credential_ids:
            # Compatibility with older Web clients sending inclusion lists.
            activities_qs = _validate_selection(
                activities_qs, selected_activity_ids or (), label="Activities",
            )
            proofs_qs = _validate_selection(
                proofs_qs, selected_proof_ids or (), label="Proofs",
            )
            credentials_qs = _validate_selection(
                credentials_qs, selected_credential_ids or (), label="Credentials",
            )
            sections = set(selected_sections or ())
        else:
            sections = public_sections
        if "interests" not in sections:
            interests_qs = interests_qs.none()
        if "open_to" not in sections:
            open_to_qs = open_to_qs.none()
    else:
        sections = {"identity", "bio", "links", "interests", "open_to"}

    identity = _profile_identity(profile)
    if public_only:
        interests_qs = tuple(row for row in interests_qs if visibility.interest(row))
        open_to_qs = tuple(row for row in open_to_qs if visibility.open_to(row))
        if not visibility.field("name"):
            identity["name"] = identity["identifier"]
        if not visibility.field("avatar"):
            identity["avatar_url"] = ""
        if not visibility.field("bio"):
            identity["bio"] = ""
        if not visibility.field("profession"):
            identity["profession"] = ""
            identity["headline"] = ""
        if not visibility.field("company_name"):
            identity["company_name"] = ""
        if not visibility.field("organization_name"):
            identity["organization_name"] = ""
        row = UserProfile.objects.filter(user=profile).first()
        identity["location"] = ", ".join(
            part for part, field in (
                (row.city if row else "", "city"),
                (row.country if row else "", "country"),
            ) if part and visibility.field(field)
        )
        identity["links"] = tuple(
            (label, url) for label, url, field in (
                ("Site web", profile.website, "website"),
                ("LinkedIn", profile.linkedin_url, "linkedin_url"),
                ("Facebook", profile.facebook_url, "facebook_url"),
                ("Instagram", profile.instagram_url, "instagram_url"),
                ("TikTok", profile.tiktok_url, "tiktok_url"),
                ("X / Twitter", profile.x_url, "x_url"),
                ("YouTube", profile.youtube_url, "youtube_url"),
            ) if url and visibility.field(field)
        )
    if thematic:
        # Themes scope activities and declarations, never the Profile's
        # identity. Its permanent identity baseline must still honor the
        # public disclosure rules, including explicit private audiences.
        thematic_visibility = ProfileVisibilityResolver(owner=profile, viewer=None)
        if not thematic_visibility.field("name"):
            identity["name"] = identity["identifier"]
        for field, key in (
            ("avatar", "avatar_url"),
            ("bio", "bio"),
            ("company_name", "company_name"),
            ("organization_name", "organization_name"),
        ):
            if not thematic_visibility.field(field):
                identity[key] = ""
        if not thematic_visibility.field("profession"):
            identity["profession"] = ""
            identity["headline"] = ""
        location_row = UserProfile.objects.filter(user=profile).first()
        identity["location"] = ", ".join(
            part for part, field in (
                (location_row.city if location_row else "", "city"),
                (location_row.country if location_row else "", "country"),
            ) if part and thematic_visibility.field(field)
        )
        identity["links"] = tuple(
            (label, url) for label, url, field in (
                ("Site web", profile.website, "website"),
                ("LinkedIn", profile.linkedin_url, "linkedin_url"),
                ("Facebook", profile.facebook_url, "facebook_url"),
                ("Instagram", profile.instagram_url, "instagram_url"),
                ("TikTok", profile.tiktok_url, "tiktok_url"),
                ("X / Twitter", profile.x_url, "x_url"),
                ("YouTube", profile.youtube_url, "youtube_url"),
            ) if url and thematic_visibility.field(field)
        )
    if public_only:
        # These are the *publicly admitted* personal facts from the same
        # Accounts fields as the owner's complete Passport. Never derive a
        # public value by hiding a widget or by copying all owner_details.
        details = {"username": identity["identifier"]}
        if visibility.field("name"):
            details.update({
                "first_name": profile.first_name or "",
                "last_name": profile.last_name or "",
            })
        profile_row = UserProfile.objects.filter(user=profile).first()
        if profile_row:
            for field in ("city", "country"):
                if visibility.field(field):
                    details[field] = getattr(profile_row, field) or ""
        identity["presentation_details"] = details
    if variant == PASSPORT_COMPLETE:
        # Full owner variant only. All other variants remain disclosure-bounded.
        profile_row = UserProfile.objects.filter(user=profile).first()
        identity["owner_details"] = {
            "first_name": profile.first_name or "",
            "last_name": profile.last_name or "",
            "username": profile.username,
            "company": profile_row.company_name or "" if profile_row else "",
            "organization": profile_row.organization_name or "" if profile_row else "",
            "city": profile_row.city or "" if profile_row else "",
            "country": profile_row.country or "" if profile_row else "",
            "phone": profile.phone or "",
            "address": profile_row.address or "" if profile_row else "",
            "birth_date": profile.birth_date.isoformat() if profile.birth_date else "",
            "gender": profile.get_gender_display() if profile.gender and profile.gender != GenderCode.UNSPECIFIED else "",
        }
    if custom:
        # Custom begins with the admissible public baseline. Include choices
        # only REMOVE parts of that baseline; they never elevate disclosure.
        for section, key in (
            ("avatar", "avatar_url"),
            ("bio", "bio"),
            ("profession", "profession"),
            ("company_name", "company_name"),
            ("organization_name", "organization_name"),
        ):
            if section not in sections:
                identity[key] = ""
        if "profession" not in sections:
            identity["headline"] = ""
        if "links" not in sections:
            identity["links"] = ()
        if "location" not in sections:
            identity["location"] = ""
            for key in ("city", "country"):
                identity["presentation_details"].pop(key, None)

    observed_at = timezone.now()
    return PassportProjection(
        subject_kind="profile",
        subject=profile,
        variant=variant,
        generated_at=observed_at,
        identity=identity,
        team_affiliations=(_profile_team_affiliations(profile) if variant == PASSPORT_COMPLETE else ()),
        group_affiliations=(_profile_group_affiliations(profile) if variant == PASSPORT_COMPLETE else ()),
        authorized_space_affiliations=(_profile_authorized_space_affiliations(profile) if variant == PASSPORT_COMPLETE else ()),
        active_space_mandates=(_profile_active_space_mandates(profile, at=observed_at) if variant == PASSPORT_COMPLETE else ()),
        interests=tuple(interests_qs),
        open_to=tuple(open_to_qs),
        activities=tuple(activities_qs),
        proofs=tuple(proofs_qs),
        credentials=tuple(credentials_qs),
        activity_involvements=tuple(
            item for item in _profile_confirmed_involvements(
                profile, public_only=public_only,
            ) if not thematic or (
                topics and any(code in {topic.code for topic in topics}
                               for code in item["topic_codes"])
            )
        ) if not custom or "activity_involvements" in sections else (),
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
    excluded_activity_ids=(),
    excluded_credential_ids=(),
    excluded_sections=(),
    include_private_teams=False,
):
    """One Space fact source, with public-by-default filtered variants.

    Custom selections only subtract admitted public facts. Legacy Web include
    lists are retained for older clients, never to elevate disclosure.
    """
    if variant not in PASSPORT_VARIANTS:
        raise ValueError("Variante Passeport inconnue.")

    public_only = variant != PASSPORT_COMPLETE
    thematic = variant == PASSPORT_THEMATIC
    custom = variant == PASSPORT_CUSTOM
    topics = _topics_from_codes(topic_codes) if thematic else ()

    activities_qs = _space_activity_queryset(space, public_only=public_only)
    credentials_qs = credentials_issued_by_space(space, valid_only=True).filter(
        activity__status__in=PASSPORT_ACTIVITY_STATUSES,
    )
    if public_only:
        credentials_qs = credentials_qs.filter(
            activity__visibility=ActivityVisibility.PUBLIC,
        )

    if thematic:
        if topics:
            activities_qs = _filter_activity_topics(activities_qs, topics, thematic=True)
            credentials_qs = credentials_qs.filter(
                activity__topic_links__topic__in=topics,
            ).distinct()
        else:
            activities_qs = activities_qs.none()
            credentials_qs = credentials_qs.none()

    sections = {"identity", "bio", "links", "location", "trust", "credentials"}
    if custom:
        if excluded_sections or excluded_activity_ids or excluded_credential_ids:
            forbidden = set(excluded_sections) - (sections - {"identity"})
            if forbidden:
                raise PassportSelectionError("Rubrique de Passeport inconnue.")
            if excluded_activity_ids:
                _validate_selection(
                    activities_qs, excluded_activity_ids, label="Activities",
                )
                activities_qs = activities_qs.exclude(
                    pk__in=excluded_activity_ids,
                )
            if excluded_credential_ids:
                _validate_selection(
                    credentials_qs, excluded_credential_ids, label="Credentials",
                )
                credentials_qs = credentials_qs.exclude(
                    pk__in=excluded_credential_ids,
                )
            sections -= set(excluded_sections)
        elif (selected_sections or selected_activity_ids is not None
              or selected_credential_ids is not None):
            # Compatibility only: the previous Web form used inclusions.
            if selected_activity_ids is not None:
                activities_qs = _validate_selection(
                    activities_qs, selected_activity_ids, label="Activities",
                )
            if selected_credential_ids is not None:
                credentials_qs = _validate_selection(
                    credentials_qs, selected_credential_ids, label="Credentials",
                )
            sections = set(selected_sections or ()) & sections

    identity = _space_identity(space)
    if variant == PASSPORT_COMPLETE:
        # Only an authorized operator may receive institutional contacts;
        # these are never copied into a public, thematic or shared selection.
        identity["owner_details"] = {
            "city": space.city or "",
            "country": space.country or "",
            "phone": space.contact_phone or "",
            "email": space.contact_email or "",
        }
    if custom:
        for key in ("bio", "links", "location"):
            if key not in sections:
                identity[key] = () if key == "links" else ""

    trust_verifications = (
        tuple(active_public_verifications_for_space(space))
        if "trust" in sections else ()
    )
    credential_summary = (
        _space_credential_summary(credentials_qs)
        if "credentials" in sections else ()
    )
    return PassportProjection(
        subject_kind="space",
        subject=space,
        variant=variant,
        generated_at=timezone.now(),
        identity=identity,
        activities=tuple(activities_qs),
        trust_verifications=trust_verifications,
        credential_summary=credential_summary,
        space_teams=(
            tuple(
                space.teams.filter(is_active=True)
                .order_by("name").values_list("name", flat=True)
            )
            if variant == PASSPORT_COMPLETE and include_private_teams else ()
        ),
        topics=topics,
    )


def profile_passport_topic_options(profile):
    activity_ids = set(
        _profile_activity_queryset(profile, public_only=False).values_list("pk", flat=True)
    )
    activity_ids.update(
        row["activity_id"] for row in _profile_confirmed_involvements(profile)
    )
    activity_ids.update(
        credentials_for_profile(profile).values_list("activity_id", flat=True)
    )
    activity_ids.update(
        proofs_for_profile(profile).filter(status=ProofStatus.ACTIVE).values_list(
            "journey__activity_id", flat=True
        )
    )
    topic_ids = set(
        ProfileInterest.objects.filter(profile=profile, topic__is_active=True).values_list("topic_id", flat=True)
    )
    # Open To is a distinct explicit declaration, not an inferred Interest.
    # Its topic must remain selectable even when the owner has no matching
    # Interest, owned Activity, Proof or Credential.
    topic_ids.update(
        ProfileOpenTo.objects.filter(
            profile=profile, is_active=True, topic__is_active=True,
        ).values_list("topic_id", flat=True)
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
        activity_links__activity__visibility=ActivityVisibility.PUBLIC,
    ).distinct().order_by("label", "code")

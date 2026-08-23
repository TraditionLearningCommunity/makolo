from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import (
    LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE,
    PermissionCode,
    SYSTEM_ROLE_TO_LEGACY_ORGANIZATION_ROLE,
    SystemRoleCode,
)
from authorization.services import (
    can,
    grant_space_role,
    replace_standard_space_role,
    revoke_all_space_mandates,
)

from .models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    Team,
    TeamMembership,
    TeamMembershipStatus,
)
from .permissions import user_can_manage_organization_team


User = get_user_model()


def _normalize_follow_preferences(values):
    normalized = {
        "notify_new_events": bool(values.get("notify_new_events", True)),
        "notify_announcements": bool(values.get("notify_announcements", True)),
        "email_new_events": bool(values.get("email_new_events", False)),
        "email_announcements": bool(values.get("email_announcements", False)),
    }
    if not normalized["notify_new_events"]:
        normalized["email_new_events"] = False
    if not normalized["notify_announcements"]:
        normalized["email_announcements"] = False
    return normalized


def ensure_default_team(organization: Organization) -> Team:
    team = organization.teams.filter(is_default=True).first()
    if team:
        if not team.is_active:
            team.is_active = True
            team.save(update_fields=["is_active", "updated_at"])
        return team
    team = Team(
        organization=organization,
        name="Équipe principale",
        is_default=True,
        is_active=True,
    )
    team.full_clean()
    team.save()
    return team


def _canonical_role_code(role_or_code: str) -> str:
    return LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE.get(role_or_code, role_or_code)


def _legacy_role_code(role_or_code: str) -> str:
    canonical = _canonical_role_code(role_or_code)
    try:
        return SYSTEM_ROLE_TO_LEGACY_ORGANIZATION_ROLE[canonical]
    except KeyError as exc:
        raise ValidationError("Rôle standard d'Espace invalide.") from exc


def _sync_legacy_membership(*, organization, user, canonical_role_code, invited_by, active=True):
    legacy_role = _legacy_role_code(canonical_role_code)
    membership, _ = OrganizationMembership.objects.update_or_create(
        organization=organization,
        user=user,
        defaults={
            "role": legacy_role,
            "is_active": active,
            "invited_by": invited_by,
        },
    )
    return membership


@transaction.atomic
def sync_legacy_membership_to_authority(membership: OrganizationMembership):
    """Project a historical OrganizationMembership into Team + Mandate.

    New application flows write TeamMembership + Mandate first. This bridge
    exists while old fixtures/API clients still write the compatibility model.
    It deliberately applies the same owner invariant as canonical services.
    """
    membership = OrganizationMembership.objects.select_related(
        "organization", "user", "invited_by"
    ).get(pk=membership.pk)
    team = ensure_default_team(membership.organization)
    team_membership, _ = TeamMembership.objects.update_or_create(
        team=team,
        user=membership.user,
        defaults={
            "status": (
                TeamMembershipStatus.ACTIVE
                if membership.is_active
                else TeamMembershipStatus.INACTIVE
            ),
            "invited_by": membership.invited_by,
            "joined_at": membership.joined_at,
        },
    )
    if not membership.is_active:
        revoke_all_space_mandates(
            profile=membership.user,
            space=membership.organization,
            actor=membership.invited_by,
        )
        return team_membership

    role_code = _canonical_role_code(membership.role)
    replace_standard_space_role(
        profile=membership.user,
        space=membership.organization,
        role_code=role_code,
        granted_by=membership.invited_by or membership.organization.created_by,
        source="legacy-membership-sync",
    )
    return team_membership


@transaction.atomic
def create_organization(*, creator, name: str, **fields) -> Organization:
    if not getattr(creator, "is_authenticated", False):
        raise PermissionDenied("Vous devez être connecté pour créer un Espace.")
    organization = Organization(created_by=creator, name=name.strip(), **fields)
    organization.full_clean()
    organization.save()

    team = ensure_default_team(organization)
    TeamMembership.objects.create(
        team=team,
        user=creator,
        status=TeamMembershipStatus.ACTIVE,
        invited_by=creator,
        joined_at=timezone.now(),
    )
    grant_space_role(
        profile=creator,
        space=organization,
        role=SystemRoleCode.SPACE_OWNER,
        granted_by=creator,
        source="space-creation",
    )
    _sync_legacy_membership(
        organization=organization,
        user=creator,
        canonical_role_code=SystemRoleCode.SPACE_OWNER,
        invited_by=creator,
        active=True,
    )
    return organization


@transaction.atomic
def ensure_personal_organization(user) -> Organization:
    team_membership = (
        TeamMembership.objects.filter(
            user=user,
            status=TeamMembershipStatus.ACTIVE,
            team__is_active=True,
        )
        .select_related("team__organization")
        .order_by("joined_at", "created_at")
        .first()
    )
    if team_membership:
        return team_membership.team.organization

    legacy = (
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization")
        .order_by("joined_at")
        .first()
    )
    if legacy:
        sync_legacy_membership_to_authority(legacy)
        return legacy.organization

    display = getattr(user, "full_name", "") or user.username or user.email.split("@")[0]
    return create_organization(
        creator=user,
        name=f"{display} Events",
        contact_email=user.email or "",
        public_profile=True,
    )


@transaction.atomic
def add_or_update_member(*, organization, actor, user, role: str) -> TeamMembership:
    if not user_can_manage_organization_team(actor, organization):
        raise PermissionDenied("Vous ne pouvez pas gérer l'équipe de cet Espace.")

    canonical_role = _canonical_role_code(role)
    if canonical_role == SystemRoleCode.SPACE_OWNER and not can(
        actor, PermissionCode.SPACE_OWNERSHIP_MANAGE, organization
    ):
        raise PermissionDenied("Seul un propriétaire peut accorder la propriété de cet Espace.")

    team = ensure_default_team(organization)
    membership, _ = TeamMembership.objects.update_or_create(
        team=team,
        user=user,
        defaults={
            "status": TeamMembershipStatus.ACTIVE,
            "invited_by": actor,
            "joined_at": timezone.now(),
        },
    )
    membership.full_clean()
    membership.save()

    replace_standard_space_role(
        profile=user,
        space=organization,
        role_code=canonical_role,
        granted_by=actor,
        source="team-service",
    )
    _sync_legacy_membership(
        organization=organization,
        user=user,
        canonical_role_code=canonical_role,
        invited_by=actor,
        active=True,
    )
    return membership


@transaction.atomic
def deactivate_member(*, membership, actor) -> TeamMembership:
    """Compatibility entrypoint for a complete departure from a Space team.

    Delegate to the Task 19 orchestration so legacy/internal callers receive
    the same ownership checks and Activity-Mandate cleanup as the Space Console.
    """
    from .team_responsibilities import remove_member_from_space

    return remove_member_from_space(membership=membership, actor=actor)


def find_user_for_team(*, email: str):
    email = email.strip().lower()
    if not email:
        raise ValidationError("L'adresse e-mail est obligatoire.")
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist as exc:
        raise ValidationError("Aucun compte Makolo ne correspond à cette adresse e-mail.") from exc


def _sync_follower_to_crm_on_commit(follow_id):
    def callback():
        from crm.services import sync_contact_from_follower

        follow = OrganizationFollow.objects.select_related("organization", "user").filter(pk=follow_id).first()
        if follow:
            sync_contact_from_follower(follow)

    transaction.on_commit(callback)


@transaction.atomic
def follow_organization(*, user, organization: Organization, **preferences) -> OrganizationFollow:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour suivre un organisateur.")
    if not organization.public_profile or organization.verification_status == "suspended":
        raise ValidationError("Cet organisateur ne peut pas être suivi actuellement.")
    current = {
        "notify_new_events": preferences.get("notify_new_events", True),
        "notify_announcements": preferences.get("notify_announcements", True),
        "email_new_events": preferences.get("email_new_events", False),
        "email_announcements": preferences.get("email_announcements", False),
    }
    defaults = _normalize_follow_preferences(current)
    follow, _ = OrganizationFollow.objects.update_or_create(
        organization=organization,
        user=user,
        defaults=defaults,
    )
    _sync_follower_to_crm_on_commit(follow.pk)
    return follow


@transaction.atomic
def update_follow_preferences(*, follow: OrganizationFollow, user, **preferences) -> OrganizationFollow:
    follow = OrganizationFollow.objects.select_for_update().select_related("organization", "user").get(pk=follow.pk)
    if follow.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Vous ne pouvez modifier que vos propres abonnements.")
    current = {
        "notify_new_events": follow.notify_new_events,
        "notify_announcements": follow.notify_announcements,
        "email_new_events": follow.email_new_events,
        "email_announcements": follow.email_announcements,
    }
    current.update({key: value for key, value in preferences.items() if key in current})
    normalized = _normalize_follow_preferences(current)
    changed = []
    for key, value in normalized.items():
        if getattr(follow, key) != value:
            setattr(follow, key, value)
            changed.append(key)
    if changed:
        follow.save(update_fields=changed + ["updated_at"])
        _sync_follower_to_crm_on_commit(follow.pk)
    return follow


@transaction.atomic
def unfollow_organization(*, follow: OrganizationFollow, user) -> None:
    follow = OrganizationFollow.objects.select_for_update().get(pk=follow.pk)
    if follow.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Vous ne pouvez supprimer que vos propres abonnements.")
    organization_id = follow.organization_id
    user_id = follow.user_id
    follow.delete()

    def revoke():
        from crm.services import revoke_follower_consent

        revoke_follower_consent(organization_id=organization_id, user_id=user_id)

    transaction.on_commit(revoke)

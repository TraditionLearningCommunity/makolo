from __future__ import annotations

from access.models import Access, AccessUse, AccessUseResult
from access.services import issue_access, validate_access
from accounts.models import NotificationPreference, User
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, replace_standard_space_role
from organizations.models import Organization, TeamMembership, TeamMembershipStatus
from transport.models import TransportDeparture

from .common import SeedContext, upsert


T22_PERSONAS = {
    "owner": "beta.owner@makolo.test",
    "admin": "beta.spaceadmin@makolo.test",
    "access_manager": "beta.access@makolo.test",
    "activity_local": "beta.activitylocal@makolo.test",
    "team_only": "beta.teamonly@makolo.test",
}


def _user(ctx: SeedContext, key: str, first_name: str, last_name: str) -> User:
    user = upsert(
        User,
        f"task22-{key}",
        defaults={
            "email": T22_PERSONAS[key],
            "username": f"beta_{key}",
            "first_name": first_name,
            "last_name": last_name,
            "language": "fr",
            "timezone": "Africa/Lubumbashi",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "is_verified": True,
            "email_verified": True,
            "is_organizer": key in {"owner", "admin", "activity_local"},
            "is_scanner_agent": False,
            "onboarding_completed": True,
            "onboarding_step": 5,
            "metadata": {"seed": "makolo-beta", "persona": key, "task": "22"},
        },
    )
    user.set_password(ctx.demo_password)
    user.save(update_fields=["password"])
    NotificationPreference.objects.update_or_create(
        user=user,
        defaults={
            "email_notifications": False,
            "sms_notifications": False,
            "push_notifications": False,
            "marketing_notifications": False,
            "security_notifications": True,
            "event_notifications": True,
        },
    )
    return user


def _team_member(space: Organization, user: User, inviter: User) -> None:
    team = space.primary_team
    if team is None:
        raise RuntimeError(f"Espace bêta sans équipe par défaut: {space.slug}")
    TeamMembership.objects.update_or_create(
        team=team,
        user=user,
        defaults={
            "status": TeamMembershipStatus.ACTIVE,
            "invited_by": inviter,
        },
    )


def _exercise_transport_access(users: dict[str, User]) -> None:
    seeded_access = (
        Access.objects.select_related("journey__activity", "journey__occurrence", "journey__beneficiary")
        .filter(source_key="beta:transport-online")
        .first()
    )
    journey = seeded_access.journey if seeded_access is not None else None
    if journey is None or journey.occurrence is None:
        raise RuntimeError("Journey Transport canonique beta:transport-online absent")

    access = issue_access(
        beneficiary=journey.beneficiary,
        activity=journey.activity,
        occurrence=journey.occurrence,
        journey=journey,
        issued_by=users["owner"],
        source_key="task22-access-use-proof",
        audit_reason="Preuve bêta T22 hors Event",
    )
    if AccessUse.objects.filter(access=access, result=AccessUseResult.ACCEPTED).exists():
        return
    credential = access.credentials.filter(status="active").order_by("issued_at", "pk").first()
    if credential is None:
        raise RuntimeError("Credential Transport canonique absent")
    outcome = validate_access(
        access=access,
        credential=credential,
        controller=users["scanner"],
        expected_activity=journey.activity,
        expected_occurrence=journey.occurrence,
        source="makolo-beta-task22",
        now=journey.occurrence.start_at,
    )
    if not outcome.accepted:
        raise RuntimeError(f"Contrôle Access Transport T22 refusé: {outcome.result}")


def seed_task22_extension(ctx: SeedContext) -> None:
    """Complete the canonical beta seed with the final T22 authority matrix.

    This deliberately composes the existing Event + Transport scenarios. It
    does not introduce a new vertical or a parallel business model.
    """
    event_space = Organization.objects.get(slug="beta-events")
    transport_space = Organization.objects.get(slug="beta-transport")
    historical_admin = User.objects.get(email=T22_PERSONAS["admin"])

    owner = _user(ctx, "owner", "Olivia", "Propriétaire")
    access_manager = _user(ctx, "access_manager", "Alex", "Accès")
    activity_local = _user(ctx, "activity_local", "Lina", "Trajet")
    team_only = _user(ctx, "team_only", "Tina", "Équipe")

    for space in (event_space, transport_space):
        _team_member(space, owner, historical_admin)
        grant_space_role(
            profile=owner,
            space=space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=historical_admin,
            source="makolo-beta-task22",
        )

    # The historical beta.spaceadmin account used to double as Owner. T22 makes
    # the demo distinction explicit while preserving the stable login address.
    for space in (event_space, transport_space):
        replace_standard_space_role(
            profile=historical_admin,
            space=space,
            role_code=SystemRoleCode.SPACE_ADMIN,
            granted_by=owner,
            source="makolo-beta-task22",
        )

    _team_member(event_space, access_manager, owner)
    grant_space_role(
        profile=access_manager,
        space=event_space,
        role=SystemRoleCode.ACCESS_MANAGER,
        granted_by=owner,
        source="makolo-beta-task22",
    )

    local_departure = (
        TransportDeparture.objects.select_related("occurrence__activity")
        .filter(occurrence__activity__space=transport_space, occurrence__status="scheduled")
        .order_by("occurrence__start_at")
        .first()
    )
    if local_departure is None:
        raise RuntimeError("Départ Transport bêta futur absent")
    _team_member(transport_space, activity_local, owner)
    grant_activity_role(
        profile=activity_local,
        activity=local_departure.occurrence.activity,
        role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        granted_by=owner,
        source="makolo-beta-task22",
    )

    # TeamMembership proves collaboration only: this persona intentionally has
    # no Mandate and therefore no authority over the Espace.
    _team_member(event_space, team_only, owner)

    _exercise_transport_access(
        {
            "owner": owner,
            "scanner": User.objects.get(email="beta.scanner@makolo.test"),
        }
    )
    ctx.add("task22_personas", 4)
    ctx.add("task22_team_only_members", 1)
    ctx.add("task22_non_event_access_uses", 1)

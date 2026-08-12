from __future__ import annotations

from authorization.services import ensure_platform_admin_mandate
from organizations.models import OrganizationMembership
from organizations.services import sync_legacy_membership_to_authority

from .common import SeedContext


def seed_contextual_authority(ctx: SeedContext) -> None:
    """Keep the deterministic demo compatible with the canonical authority model.

    The demo still deliberately constructs historical OrganizationMembership
    rows so compatibility paths remain exercised. This pass projects their
    final/backdated state into TeamMembership + Mandate and explicitly grants
    platform authority to the three demo Operations profiles.
    """
    for membership in OrganizationMembership.objects.select_related(
        "organization", "user", "invited_by"
    ).iterator():
        sync_legacy_membership_to_authority(membership)

    for profile in ctx.staff_users:
        ensure_platform_admin_mandate(
            profile=profile,
            source="makolo-demo",
        )

    ctx.add("contextual_mandates", sum(profile.authority_mandates.count() for profile in ctx.users))

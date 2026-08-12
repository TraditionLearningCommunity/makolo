import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership, OrganizationRole, TeamMembership

from .constants import SystemRoleCode
from .models import AuthorityScope, Mandate, MandateStatus


User = get_user_model()


class AuthorityBackfillTests(TestCase):
    def test_data_migration_maps_every_legacy_role_and_existing_staff(self):
        creator = User.objects.create_user(
            username="legacy-owner",
            email="legacy-owner@makolo.test",
            password="StrongPass2026!",
        )
        staff = User.objects.create_user(
            username="legacy-staff",
            email="legacy-staff@makolo.test",
            password="StrongPass2026!",
            is_staff=True,
        )
        space = Organization.objects.create(name="Legacy Space", created_by=creator)

        expected = {
            OrganizationRole.OWNER: SystemRoleCode.SPACE_OWNER,
            OrganizationRole.ADMIN: SystemRoleCode.SPACE_ADMIN,
            OrganizationRole.EVENT_MANAGER: SystemRoleCode.ACTIVITY_MANAGER,
            OrganizationRole.FINANCE: SystemRoleCode.FINANCE,
            OrganizationRole.MARKETING: SystemRoleCode.MARKETING,
            OrganizationRole.SCANNER_MANAGER: SystemRoleCode.ACCESS_MANAGER,
        }
        rows = []
        users = {}
        for index, legacy_role in enumerate(expected):
            profile = creator if legacy_role == OrganizationRole.OWNER else User.objects.create_user(
                username=f"legacy-{index}",
                email=f"legacy-{index}@makolo.test",
                password="StrongPass2026!",
            )
            users[legacy_role] = profile
            rows.append(
                OrganizationMembership(
                    organization=space,
                    user=profile,
                    role=legacy_role,
                    is_active=True,
                    invited_by=creator if profile != creator else None,
                )
            )
        # bulk_create intentionally bypasses the compatibility post_save bridge so
        # this test exercises the versioned data migration itself.
        OrganizationMembership.objects.bulk_create(rows)

        migration = importlib.import_module("authorization.migrations.0002_seed_roles_and_backfill")
        migration.seed_and_backfill(apps, None)

        self.assertEqual(space.teams.filter(is_default=True).count(), 1)
        self.assertEqual(
            TeamMembership.objects.filter(team__organization=space, status="active").count(),
            len(expected),
        )
        for legacy_role, canonical_role in expected.items():
            self.assertTrue(
                Mandate.objects.filter(
                    profile=users[legacy_role],
                    space=space,
                    scope_type=AuthorityScope.SPACE,
                    status=MandateStatus.ACTIVE,
                    role__code=canonical_role,
                ).exists(),
                f"{legacy_role} -> {canonical_role}",
            )

        self.assertTrue(
            Mandate.objects.filter(
                profile=staff,
                scope_type=AuthorityScope.PLATFORM,
                space__isnull=True,
                status=MandateStatus.ACTIVE,
                role__code=SystemRoleCode.PLATFORM_ADMIN,
            ).exists()
        )

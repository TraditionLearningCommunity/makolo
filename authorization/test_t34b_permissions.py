from django.contrib.auth import get_user_model
from django.test import TestCase

from .constants import (
    ACTIVITY_PERMISSION_CODES,
    PLATFORM_PERMISSION_CODES,
    SPACE_PERMISSION_CODES,
    PermissionCode,
    SystemRoleCode,
)
from .models import AuthorityScope, Role
from .platform_services import grant_platform_role
from .services import can, get_system_role


User = get_user_model()


SERVICE_CODES = {
    PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
    PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
    PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL,
    PermissionCode.ACTIVITY_SERVICES_OUTCOMES_MANAGE,
    PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY,
}

OPPORTUNITY_CODES = {
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}


class T34BPermissionClassificationTests(TestCase):
    def test_services_permissions_are_activity_only(self):
        self.assertTrue(SERVICE_CODES <= ACTIVITY_PERMISSION_CODES)
        self.assertTrue(SERVICE_CODES.isdisjoint(SPACE_PERMISSION_CODES))

    def test_opportunity_permissions_are_platform_only(self):
        self.assertTrue(OPPORTUNITY_CODES <= PLATFORM_PERMISSION_CODES)
        self.assertTrue(OPPORTUNITY_CODES.isdisjoint(SPACE_PERMISSION_CODES))

    def test_no_journey_authority_scope_exists(self):
        self.assertNotIn("journey", AuthorityScope.values)


class T34BSystemRoleBundleTests(TestCase):
    def _permission_codes(self, role_code, scope_type):
        role = get_system_role(role_code, scope_type=scope_type)
        return set(role.role_permissions.values_list("permission__code", flat=True))

    def test_service_manager_is_least_privilege_without_restricted_view(self):
        codes = self._permission_codes(SystemRoleCode.ACTIVITY_SERVICE_MANAGER, AuthorityScope.ACTIVITY)
        self.assertIn(PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL, codes)
        self.assertIn(PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY, codes)
        self.assertNotIn(PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW, codes)
        self.assertNotIn(PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED, codes)

    def test_service_facilitator_is_assignment_scoped(self):
        codes = self._permission_codes(SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR, AuthorityScope.ACTIVITY)
        self.assertIn(PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED, codes)
        self.assertIn(PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE, codes)
        self.assertNotIn(PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL, codes)
        self.assertNotIn(PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY, codes)
        self.assertNotIn(PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW, codes)

    def test_service_reviewer_can_review_restricted_without_case_mutation(self):
        codes = self._permission_codes(SystemRoleCode.ACTIVITY_SERVICE_REVIEWER, AuthorityScope.ACTIVITY)
        self.assertEqual(
            codes,
            {
                PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
                PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW,
                PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
                PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE,
            },
        )

    def test_opportunity_curator_bundle_is_platform_scoped_and_atomic(self):
        role = get_system_role(SystemRoleCode.OPPORTUNITY_CURATOR, scope_type=AuthorityScope.PLATFORM)
        self.assertEqual(role.scope_type, AuthorityScope.PLATFORM)
        self.assertEqual(set(role.role_permissions.values_list("permission__code", flat=True)), OPPORTUNITY_CODES)


class T34BPlatformGrantTests(TestCase):
    def test_generic_platform_grant_is_idempotent_and_permission_scoped(self):
        profile = User.objects.create_user(
            username="opportunity-curator",
            email="opportunity-curator@makolo.test",
            password="StrongPass2026!",
        )
        role = Role.objects.get(code=SystemRoleCode.OPPORTUNITY_CURATOR, scope_type=AuthorityScope.PLATFORM)
        first = grant_platform_role(profile=profile, role=role, source="t34b-test")
        second = grant_platform_role(profile=profile, role=role, source="t34b-test")
        self.assertEqual(first.pk, second.pk)
        self.assertTrue(can(profile, PermissionCode.OPPORTUNITIES_MANAGE))
        self.assertTrue(can(profile, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY))
        self.assertFalse(can(profile, PermissionCode.PLATFORM_MANAGE))

    def test_platform_admin_still_expands_to_new_permissions(self):
        profile = User.objects.create_user(
            username="platform-admin-t34b",
            email="platform-admin-t34b@makolo.test",
            password="StrongPass2026!",
        )
        grant_platform_role(profile=profile, role=SystemRoleCode.PLATFORM_ADMIN, source="t34b-test")
        for code in OPPORTUNITY_CODES:
            self.assertTrue(can(profile, code), code)

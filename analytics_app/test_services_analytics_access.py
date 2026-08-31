from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, Permission, Role, RolePermission
from organizations.models import Organization
from services.models import ServiceDetails, ServiceKind

from .selectors import get_service_analytics_activities


User = get_user_model()


class ServiceAnalyticsAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "services-owner",
            "services-owner@example.com",
            "Analytics-2026!",
        )
        self.viewer = User.objects.create_user(
            "services-analytics-viewer",
            "services-analytics-viewer@example.com",
            "Analytics-2026!",
        )
        self.outsider = User.objects.create_user(
            "services-outsider",
            "services-outsider@example.com",
            "Analytics-2026!",
        )
        self.space = Organization.objects.create(
            name="Services analytics access space",
            created_by=self.owner,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Service analytics access",
        )
        ServiceDetails.objects.create(
            activity=self.activity,
            service_kind=ServiceKind.OTHER,
        )

        analytics_view, _ = Permission.objects.get_or_create(
            code=PermissionCode.ANALYTICS_VIEW,
            defaults={
                "name": "View analytics",
                "domain": "analytics",
                "scope_type": AuthorityScope.SPACE,
            },
        )
        role = Role.objects.create(
            code="services-analytics-view-only",
            name="Services analytics view only",
            scope_type=AuthorityScope.SPACE,
            organization=self.space,
            is_system=False,
        )
        RolePermission.objects.create(role=role, permission=analytics_view)
        Mandate.objects.create(
            profile=self.viewer,
            role=role,
            scope_type=AuthorityScope.SPACE,
            space=self.space,
            granted_by=self.owner,
            source="t36-test",
        )

    def test_selector_requires_canonical_analytics_authority(self):
        self.assertTrue(get_service_analytics_activities(self.viewer).filter(pk=self.activity.pk).exists())
        self.assertFalse(get_service_analytics_activities(self.outsider).filter(pk=self.activity.pk).exists())

    def test_api_does_not_leak_financials_to_analytics_only_role(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("analytics_api:service-activity-detail", kwargs={"pk": self.activity.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["financial_visible"])
        self.assertIsNone(response.json()["metrics"]["payments"]["financials"])

    def test_api_returns_not_found_outside_authorized_scope(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("analytics_api:service-activity-detail", kwargs={"pk": self.activity.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_personal_service_uses_owner_profile_not_creator_provenance(self):
        personal_owner = User.objects.create_user(
            "personal-services-owner",
            "personal-services-owner@example.com",
            "Analytics-2026!",
        )
        creator = User.objects.create_user(
            "personal-services-creator",
            "personal-services-creator@example.com",
            "Analytics-2026!",
        )
        personal = Activity.objects.create(
            owner_profile=personal_owner,
            created_by=creator,
            title="Personal Service",
        )
        ServiceDetails.objects.create(activity=personal, service_kind=ServiceKind.OTHER)

        self.assertTrue(get_service_analytics_activities(personal_owner).filter(pk=personal.pk).exists())
        self.assertFalse(get_service_analytics_activities(creator).filter(pk=personal.pk).exists())

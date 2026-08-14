from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity
from organizations.models import Organization

from .constants import PermissionCode, SystemRoleCode
from .services import activity_ids_with_permission, can, grant_space_role


User = get_user_model()


class JourneyAccessActivityInheritanceTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="journey-access-space-creator",
            email="journey-access-space-creator@example.com",
            password="Authority-2026!",
        )
        self.manager = User.objects.create_user(
            username="journey-access-space-manager",
            email="journey-access-space-manager@example.com",
            password="Authority-2026!",
        )
        self.space = Organization.objects.create(
            name="Journey Access Space A",
            created_by=self.creator,
        )
        self.other_space = Organization.objects.create(
            name="Journey Access Space B",
            created_by=self.creator,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Activity A",
        )
        self.other_activity = Activity.objects.create(
            space=self.other_space,
            created_by=self.creator,
            title="Activity B",
        )
        grant_space_role(
            profile=self.manager,
            space=self.space,
            role=SystemRoleCode.ACTIVITY_MANAGER,
        )

    def test_space_activity_manager_inherits_request_and_access_permissions(self):
        for permission in (
            PermissionCode.ACTIVITY_REQUESTS_VIEW,
            PermissionCode.ACTIVITY_REQUESTS_DECIDE,
            PermissionCode.ACTIVITY_ACCESS_VIEW,
            PermissionCode.ACTIVITY_ACCESS_MANAGE,
        ):
            self.assertTrue(can(self.manager, permission, activity=self.activity))
            self.assertFalse(can(self.manager, permission, activity=self.other_activity))

    def test_inherited_selectors_return_only_activities_in_managed_space(self):
        for permission in (
            PermissionCode.ACTIVITY_REQUESTS_VIEW,
            PermissionCode.ACTIVITY_ACCESS_VIEW,
            PermissionCode.ACTIVITY_REQUESTS_DECIDE,
            PermissionCode.ACTIVITY_ACCESS_MANAGE,
        ):
            activity_ids = activity_ids_with_permission(self.manager, permission)
            self.assertIn(self.activity.pk, activity_ids)
            self.assertNotIn(self.other_activity.pk, activity_ids)

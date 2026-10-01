from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.services import create_activity
from authorization.services import ensure_platform_admin_mandate
from operations.models import OperationsAuditLog

from .models import SpaceLifecycle
from .services import archive_space, create_organization, restore_space, suspend_space


User = get_user_model()


class SpaceLifecycleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="space-lifecycle-owner",
            email="space-lifecycle-owner@test.local",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="space-lifecycle-outsider",
            email="space-lifecycle-outsider@test.local",
            password="StrongPass2026!",
        )
        self.staff = User.objects.create_user(
            username="space-lifecycle-staff",
            email="space-lifecycle-staff@test.local",
            password="StrongPass2026!",
            is_staff=True,
        )
        ensure_platform_admin_mandate(profile=self.staff, source="space-lifecycle-test")
        self.space = create_organization(creator=self.owner, name="Lifecycle Space")

    def test_new_space_is_active(self):
        self.assertEqual(self.space.lifecycle, SpaceLifecycle.ACTIVE)

    def test_archive_preserves_history_and_blocks_new_activity_until_restore(self):
        activity = create_activity(
            created_by=self.owner,
            space=self.space,
            title="Fait historique conservé",
        )
        archived = archive_space(space=self.space, actor=self.owner)
        self.assertEqual(archived.lifecycle, SpaceLifecycle.ARCHIVED)
        self.assertTrue(archived.activities.filter(pk=activity.pk).exists())
        with self.assertRaises(ValidationError):
            create_activity(
                created_by=self.owner,
                space=archived,
                title="Nouvelle activité interdite",
            )
        restored = restore_space(space=archived, actor=self.owner)
        self.assertEqual(restored.lifecycle, SpaceLifecycle.ACTIVE)
        self.assertTrue(
            OperationsAuditLog.objects.filter(
                target_id=str(self.space.pk),
                action="organization.lifecycle_changed",
            ).exists()
        )

    def test_outsider_cannot_archive(self):
        with self.assertRaises(PermissionDenied):
            archive_space(space=self.space, actor=self.outsider)

    def test_platform_suspension_blocks_new_activity_and_owner_restore(self):
        suspended = suspend_space(space=self.space, actor=self.staff)
        self.assertEqual(suspended.lifecycle, SpaceLifecycle.SUSPENDED)
        with self.assertRaises(ValidationError):
            create_activity(
                created_by=self.owner,
                space=suspended,
                title="Nouvelle activité interdite",
            )
        with self.assertRaises(PermissionDenied):
            restore_space(space=suspended, actor=self.owner)
        restored = restore_space(space=suspended, actor=self.staff, source="operations")
        self.assertEqual(restored.lifecycle, SpaceLifecycle.ACTIVE)

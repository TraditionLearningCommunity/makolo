from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.services import delete_account, get_account_deletion_blockers
from groups.services import archive_group, create_group


User = get_user_model()
PASSWORD = "Password123!"


class PersonalGroupAccountContinuityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="personal-group-delete-owner",
            email="personal-group-delete-owner@example.com",
            password=PASSWORD,
        )
        self.group = create_group(actor=self.owner, name="Groupe à transmettre")

    def test_active_personal_group_blocks_account_deletion(self):
        self.assertIn(self.group, get_account_deletion_blockers(self.owner))
        with self.assertRaises(ValidationError):
            delete_account(user=self.owner, current_password=PASSWORD)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_archived_personal_group_no_longer_blocks_account_deletion(self):
        archive_group(actor=self.owner, group=self.group)
        self.assertNotIn(self.group, get_account_deletion_blockers(self.owner))
        result = delete_account(user=self.owner, current_password=PASSWORD)
        self.assertEqual(result["status"], "deleted")
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_active)

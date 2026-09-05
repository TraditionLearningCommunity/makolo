from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from .models import Access, AccessCredential, AccessUse


User = get_user_model()


class PreM7AccessAdminSecurityTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="pre-m7-access-superuser",
            email="pre-m7-access-superuser@example.com",
            password="test-pass-2026",
        )
        self.request = RequestFactory().get("/admin/access/")
        self.request.user = self.superuser

    def test_access_transactional_objects_are_not_mutable_through_generic_admin(self):
        for model in (Access, AccessCredential, AccessUse):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(self.request))
            self.assertFalse(model_admin.has_change_permission(self.request))
            self.assertFalse(model_admin.has_delete_permission(self.request))

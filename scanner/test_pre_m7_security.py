from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .tests import ScannerFixtureMixin


User = get_user_model()


class PreM7ScannerAuthorityTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.staff = User.objects.create_user(
            username="pre-m7-scanner-staff",
            email="pre-m7-scanner-staff@example.com",
            password=self.password,
            is_staff=True,
        )

    def test_simple_staff_without_mandate_cannot_manage_gates_or_assignments(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("scanner:gates")).status_code, 403)
        self.assertEqual(self.client.get(reverse("scanner:assignments")).status_code, 403)

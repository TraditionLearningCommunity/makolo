from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from .models import CapacityReservation


User = get_user_model()


class PreM7CapacityAdminSecurityTests(TestCase):
    def test_capacity_reservation_is_not_mutable_through_generic_admin(self):
        user = User.objects.create_superuser(
            username="pre-m7-capacity-superuser",
            email="pre-m7-capacity-superuser@example.com",
            password="test-pass-2026",
        )
        request = RequestFactory().get("/admin/capacity/")
        request.user = user
        model_admin = admin.site._registry[CapacityReservation]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

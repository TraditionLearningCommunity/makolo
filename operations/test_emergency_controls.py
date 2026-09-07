from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from access.models import Access
from automation.scheduler import run_autopilot_cycle
from payments.models import Payment

from .emergency_controls import (
    OperationalControlDisabled,
    is_operational_control_enabled,
    set_operational_control,
)
from .emergency_signals import (
    guard_access_creation,
    guard_payment_creation,
    guard_user_creation,
)
from .models import OperationalControl, OperationalControlCode, OperationsAuditLog


User = get_user_model()


class OperationalControlTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="ops-control-admin",
            email="ops-control-admin@makolo.test",
            password="Strong-ops-control-password-2026!",
        )
        self.member = User.objects.create_user(
            username="ops-control-member",
            email="ops-control-member@makolo.test",
            password="Strong-ops-control-password-2026!",
        )

    def _set(self, code, enabled, reason="Test Operations"):
        return set_operational_control(
            code=code,
            enabled=enabled,
            actor=self.admin,
            reason=reason,
        )

    def test_controls_are_seeded_enabled(self):
        self.assertEqual(
            set(OperationalControl.objects.values_list("code", flat=True)),
            set(OperationalControlCode.values),
        )
        for code in OperationalControlCode.values:
            self.assertTrue(is_operational_control_enabled(code))

    def test_only_platform_authority_can_change_control(self):
        with self.assertRaises(PermissionDenied):
            set_operational_control(
                code=OperationalControlCode.ACCESS_ISSUANCE,
                enabled=False,
                actor=self.member,
                reason="Tentative non autorisée",
            )

    def test_disable_and_enable_are_both_audited(self):
        self._set(OperationalControlCode.ACCESS_ISSUANCE, False, "Incident Access")
        self.assertFalse(is_operational_control_enabled(OperationalControlCode.ACCESS_ISSUANCE))
        self._set(OperationalControlCode.ACCESS_ISSUANCE, True, "Incident résolu")
        self.assertTrue(is_operational_control_enabled(OperationalControlCode.ACCESS_ISSUANCE))

        actions = list(
            OperationsAuditLog.objects.filter(
                target_type="operational_control",
                target_id=OperationalControlCode.ACCESS_ISSUANCE,
            )
            .order_by("created_at")
            .values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            ["operational_control.disabled", "operational_control.enabled"],
        )

    def test_signup_guard_blocks_regular_profiles_but_not_recovery_staff(self):
        self._set(OperationalControlCode.USER_SIGNUPS, False, "Abus inscription")
        with self.assertRaises(OperationalControlDisabled):
            guard_user_creation(
                sender=User,
                instance=User(username="blocked-user", email="blocked-user@makolo.test"),
                raw=False,
            )

        recovery_staff = User(
            username="recovery-staff",
            email="recovery-staff@makolo.test",
            is_staff=True,
        )
        guard_user_creation(sender=User, instance=recovery_staff, raw=False)

        self._set(OperationalControlCode.USER_SIGNUPS, True, "Abus contenu")
        guard_user_creation(
            sender=User,
            instance=User(username="allowed-user", email="allowed-user@makolo.test"),
            raw=False,
        )

    def test_access_and_payment_creation_guards_follow_controls(self):
        self._set(OperationalControlCode.ACCESS_ISSUANCE, False, "Incident Access")
        with self.assertRaises(OperationalControlDisabled):
            guard_access_creation(sender=Access, instance=Access(), raw=False)

        self._set(OperationalControlCode.PAYMENT_CREATION, False, "Incident Payment")
        with self.assertRaises(OperationalControlDisabled):
            guard_payment_creation(sender=Payment, instance=Payment(), raw=False)

    def test_autopilot_control_short_circuits_scheduler(self):
        self._set(OperationalControlCode.AUTOPILOT, False, "Incident automation")
        with patch("automation.scheduler.run_legacy_autopilot_cycle") as legacy_cycle:
            stats = run_autopilot_cycle(delivery_limit=1)
        self.assertEqual(stats, {"operational_control": "disabled"})
        legacy_cycle.assert_not_called()

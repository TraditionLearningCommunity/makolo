from django.apps import apps
from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from events.models import Event, EventStatus
from operations.models import OperationsIncident
from payments.models import Payment, Refund
from scanner.models import ScanLog
from tickets.models import TicketOrder, TicketTransfer, TicketWaitlistEntry

from demo_seed.common import PROJECT_APPS


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MakoloDemoSeedTests(TestCase):
    def _counts(self):
        return {
            model._meta.label: model.objects.count()
            for model in apps.get_models()
            if model._meta.app_label in PROJECT_APPS
            and not model._meta.proxy
            and not model._meta.auto_created
        }

    def test_seed_covers_every_business_model_and_core_scenarios(self):
        call_command(
            "seed_makolo_demo",
            scale="small",
            as_of="2026-08-10",
            demo_password="Test-Demo-Password-2026!",
            verbosity=0,
        )

        counts = self._counts()
        missing = [label for label, count in counts.items() if count == 0]
        self.assertEqual(missing, [], msg=f"Modèles non couverts: {missing}")

        self.assertTrue(Event.objects.filter(start_at__year=2024).exists())
        self.assertTrue(Event.objects.filter(start_at__year=2027).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.COMPLETED).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.PUBLISHED).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.DRAFT).exists())
        self.assertTrue(Event.objects.filter(status=EventStatus.CANCELLED).exists())

        self.assertGreater(TicketOrder.objects.count(), 50)
        self.assertGreater(Payment.objects.count(), 20)
        self.assertTrue(Refund.objects.exists())
        self.assertTrue(TicketWaitlistEntry.objects.exists())
        self.assertTrue(TicketTransfer.objects.exists())
        self.assertTrue(ScanLog.objects.filter(result="accepted").exists())
        self.assertTrue(ScanLog.objects.filter(result="duplicate").exists())
        self.assertTrue(ScanLog.objects.filter(result="invalid_token").exists())
        self.assertTrue(OperationsIncident.objects.exists())

        demo_admin = User.objects.get(email="demo.user001@makolo.test")
        self.assertTrue(demo_admin.is_superuser)
        self.assertTrue(demo_admin.check_password("Test-Demo-Password-2026!"))

    def test_seed_is_idempotent_for_same_scale(self):
        kwargs = {
            "scale": "small",
            "as_of": "2026-08-10",
            "demo_password": "Test-Demo-Password-2026!",
            "verbosity": 0,
        }
        call_command("seed_makolo_demo", **kwargs)
        before = self._counts()
        call_command("seed_makolo_demo", **kwargs)
        after = self._counts()
        drift = {
            label: (before.get(label, 0), after.get(label, 0))
            for label in sorted(set(before) | set(after))
            if before.get(label, 0) != after.get(label, 0)
        }
        self.assertEqual(drift, {}, msg=f"Le second seed a modifié les volumes: {drift}")

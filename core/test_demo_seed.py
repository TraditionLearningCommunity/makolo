from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from demo_seed.beta import BETA_PERSONAS
from demo_seed.beta_validation import assert_beta_scenario_coverage
from seed_makolo_demo import _parse_as_of


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MakoloDemoSeedTests(TestCase):
    as_of = "2026-08-21"
    password = "Test-Demo-Password-2026!"

    def test_beta_seed_uses_semantic_personas_and_scenario_contract(self):
        call_command(
            "seed_makolo_demo",
            scale="beta",
            as_of=self.as_of,
            demo_password=self.password,
            verbosity=0,
        )

        report = assert_beta_scenario_coverage(as_of=_parse_as_of(self.as_of))
        self.assertEqual(report["personas"], len(BETA_PERSONAS))
        self.assertGreaterEqual(report["future_event_occurrences"], 5)
        self.assertGreaterEqual(report["future_transport_occurrences"], 5)

        admin = User.objects.get(email=BETA_PERSONAS["staff"])
        participant = User.objects.get(email=BETA_PERSONAS["participant"])
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(self.password))
        self.assertTrue(participant.check_password(self.password))

    def test_beta_persona_addresses_are_stable_and_fictitious(self):
        self.assertEqual(
            set(BETA_PERSONAS.values()),
            {
                "beta.admin@makolo.test",
                "beta.spaceadmin@makolo.test",
                "beta.eventmanager@makolo.test",
                "beta.transport@makolo.test",
                "beta.finance@makolo.test",
                "beta.scanner@makolo.test",
                "beta.participant@makolo.test",
                "beta.marketing@makolo.test",
            },
        )
        self.assertTrue(all(email.endswith(".test") for email in BETA_PERSONAS.values()))

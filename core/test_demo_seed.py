from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from authorization.constants import PermissionCode
from authorization.services import can
from demo_seed.beta import BETA_PERSONAS
from demo_seed.beta_validation import assert_beta_scenario_coverage
from demo_seed.task22_extension import T22_PERSONAS
from events.models import Event
from seed_makolo_demo import _parse_as_of
from transport.models import TransportService


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
        expected_personas = set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values())
        self.assertEqual(report["personas"], len(expected_personas))
        self.assertGreaterEqual(report["future_event_occurrences"], 5)
        self.assertGreaterEqual(report["future_transport_occurrences"], 5)
        self.assertGreater(report["non_event_activities"], 0)
        self.assertGreater(report["non_event_occurrences"], 0)
        self.assertGreater(report["non_event_journeys"], 0)
        self.assertGreater(report["non_event_orders"], 0)
        self.assertGreater(report["non_event_payments"], 0)
        self.assertGreater(report["non_event_accesses"], 0)
        self.assertGreater(report["non_event_access_uses"], 0)

        admin = User.objects.get(email=BETA_PERSONAS["staff"])
        participant = User.objects.get(email=BETA_PERSONAS["participant"])
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(self.password))
        self.assertTrue(participant.check_password(self.password))

    def test_task22_personas_match_their_real_authority(self):
        call_command(
            "seed_makolo_demo",
            scale="beta",
            as_of=self.as_of,
            demo_password=self.password,
            verbosity=0,
        )

        event_space = User.objects.get(email=T22_PERSONAS["owner"]).team_memberships.get(
            team__organization__slug="beta-events"
        ).team.organization
        owner = User.objects.get(email=T22_PERSONAS["owner"])
        space_admin = User.objects.get(email=T22_PERSONAS["admin"])
        access_manager = User.objects.get(email=T22_PERSONAS["access_manager"])
        team_only = User.objects.get(email=T22_PERSONAS["team_only"])

        self.assertTrue(can(owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space))
        self.assertTrue(can(space_admin, PermissionCode.SPACE_MANAGE, space=event_space))
        self.assertFalse(can(space_admin, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space))
        self.assertTrue(can(access_manager, PermissionCode.ACCESS_MANAGE, space=event_space))
        self.assertFalse(can(access_manager, PermissionCode.FINANCE_VIEW, space=event_space))
        self.assertTrue(team_only.team_memberships.filter(team__organization=event_space).exists())
        self.assertFalse(can(team_only, PermissionCode.SPACE_VIEW, space=event_space))

    def test_transport_activity_is_explicitly_not_an_event(self):
        call_command(
            "seed_makolo_demo",
            scale="beta",
            as_of=self.as_of,
            demo_password=self.password,
            verbosity=0,
        )
        transport_activity_ids = list(TransportService.objects.values_list("activity_id", flat=True))
        self.assertTrue(transport_activity_ids)
        self.assertFalse(Event.objects.filter(activity_id__in=transport_activity_ids).exists())

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
        self.assertEqual(
            set(T22_PERSONAS.values()),
            {
                "beta.owner@makolo.test",
                "beta.spaceadmin@makolo.test",
                "beta.access@makolo.test",
                "beta.activitylocal@makolo.test",
                "beta.teamonly@makolo.test",
            },
        )
        self.assertTrue(all(email.endswith(".test") for email in set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values())))

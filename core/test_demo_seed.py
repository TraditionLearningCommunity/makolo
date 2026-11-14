from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can
from demo_seed.beta import BETA_PERSONAS
from demo_seed.mobile_mature_universe import _activity_copy, _demo_title, _opportunity_summary
from demo_seed.beta_validation import assert_beta_scenario_coverage
from demo_seed.task22_extension import T22_PERSONAS
from events.models import Event
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestStatus
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
        event = Activity.objects.get(slug="beta-event-free")
        transport = Activity.objects.get(slug="beta-transport-lub-kol")
        self.assertEqual(event.title, "Atelier communauté gratuit")
        self.assertEqual(transport.title, "Lubumbashi → Kolwezi")
        self.assertFalse(event.title.startswith(("Exemple — ", "[DEMO]")))
        self.assertFalse(transport.title.startswith(("Exemple — ", "[DEMO]")))

    def test_beta_seed_reconciles_guarded_status_snapshots_on_rerun(self):
        call_command(
            "seed_makolo_demo",
            scale="beta",
            as_of=self.as_of,
            demo_password=self.password,
            verbosity=0,
        )
        journey = Journey.objects.get(
            activity__slug="beta-event-free",
            beneficiary__email=BETA_PERSONAS["participant"],
        )
        invitation_request = JourneyRequest.objects.get(
            journey__activity__slug="beta-event-invitation",
            requester__email=BETA_PERSONAS["event_manager"],
        )

        Journey.objects.filter(pk=journey.pk).update(status=JourneyStatus.CANCELLED)
        JourneyRequest.objects.filter(pk=invitation_request.pk).update(status=RequestStatus.APPROVED)

        call_command(
            "seed_makolo_demo",
            scale="beta",
            as_of=self.as_of,
            demo_password=self.password,
            verbosity=0,
        )

        journey.refresh_from_db()
        invitation_request.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.CONFIRMED)
        self.assertEqual(invitation_request.status, RequestStatus.PENDING)
        assert_beta_scenario_coverage(as_of=_parse_as_of(self.as_of))

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
                "beta.personal@makolo.test",
                "beta.personaldelegate@makolo.test",
            },
        )
        self.assertTrue(all(email.endswith(".test") for email in set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values())))


class DemoProductLanguageTests(SimpleTestCase):
    def test_mobile_scenarios_are_identified_without_erasing_their_title(self):
        self.assertEqual(
            _demo_title("Festival musical à Lubumbashi"),
            "Festival musical à Lubumbashi",
        )
        self.assertEqual(
            _demo_title("Exemple — Festival musical à Lubumbashi"),
            "Festival musical à Lubumbashi",
        )

    def test_mobile_activity_copy_is_contextual_not_one_generic_formula(self):
        spec = {
            "title": "Atelier de prise de parole",
            "geo": "Lubumbashi",
        }
        event_short, event_detail = _activity_copy(spec, "event")
        transport_short, transport_detail = _activity_copy(
            {"title": "Lubumbashi → Kolwezi", "geo": "Lubumbashi→Kolwezi"},
            "transport",
        )
        self.assertIn("participation", event_short)
        self.assertIn("Atelier de prise de parole", event_detail)
        self.assertIn("départ", transport_short)
        self.assertIn("Lubumbashi → Kolwezi", transport_detail)
        self.assertNotEqual(event_detail, transport_detail)
        self.assertNotIn("horaire confirmé", event_detail.lower())

    def test_fictitious_opportunity_copy_varies_by_actual_scenario(self):
        base = {"title": "Formation professionnelle", "geo": "Lubumbashi"}
        engaged = _opportunity_summary({**base, "relation": "engaged"})
        ineligible = _opportunity_summary({**base, "relation": "not_eligible"})
        self.assertNotEqual(engaged, ineligible)
        self.assertIn("dossier déjà commencé", engaged)
        self.assertIn("vérifier les critères", ineligible)
        self.assertIn("fictifs", engaged)
        self.assertIn("aucune candidature réelle", engaged)
        self.assertNotIn("Alain", engaged)

    def test_public_demo_opportunity_does_not_claim_a_personal_journey_or_real_offer(self):
        summary = _opportunity_summary({
            "title": "Formation professionnelle",
            "relation": "engaged",
            "state": "ongoing",
            "geo": "Lubumbashi",
        })
        self.assertIn("exemples de Makolo", summary)
        self.assertIn("fictifs", summary)
        self.assertNotIn("Alain", summary)
        self.assertNotIn("actuellement ouverte", summary)

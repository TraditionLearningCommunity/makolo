"""L1/L2 contracts: simultaneous legitimate relations, no role switch, no false Live."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from authorization.constants import PermissionCode

from .occurrence_experience import resolve_occurrence_experience
from .occurrence_experience_facts import compose_live_knowledge


class OccurrenceExperienceCompositionTests(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()
        self.viewer = SimpleNamespace(is_authenticated=True, pk="viewer")
        self.activity = SimpleNamespace(pk="activity", space_id=None)
        self.occurrence = SimpleNamespace(
            pk="occurrence",
            activity_id="activity",
            activity=self.activity,
            label="Session",
            status="scheduled",
            live_enabled=True,
            start_at=self.now + timedelta(minutes=20),
            end_at=self.now + timedelta(hours=2),
            timezone="Africa/Kinshasa",
        )

    def _resolve(
        self, *, participant=None, operator=None, institutional=None,
        owner_operations=False, finance=False, scanner=False, platform=False,
        phase="live", surface="day_of", extra_grants=(), live_enabled=True,
    ):
        self.occurrence.live_enabled = live_enabled
        institutional = [] if institutional is None else institutional
        def owner_permission(_viewer, _occurrence, permission, _space_permission=None):
            return (
                (permission == PermissionCode.ACTIVITY_FINANCE_VIEW and finance)
                or (permission == PermissionCode.ACTIVITY_OPERATIONS_VIEW and owner_operations)
                or permission in extra_grants
            )

        with (
            patch("operations.occurrence_experience.occurrence_live_phase", return_value=phase),
            patch("operations.occurrence_experience.resolve_participant_occurrence_live", return_value=participant),
            patch("operations.occurrence_experience.user_can_view_activity_operations", return_value=operator is not None),
            patch("operations.occurrence_experience.resolve_occurrence_live", return_value=operator),
            patch("operations.occurrence_experience._owner_permission", side_effect=owner_permission),
            patch("operations.occurrence_experience.user_can_manage_activity_operations", return_value=False),
            patch("operations.occurrence_experience.user_can_scan_activity", return_value=scanner),
            patch("operations.occurrence_experience.has_platform_authority", return_value=platform),
            patch("operations.occurrence_experience._institutional_journeys", return_value=institutional),
            patch("operations.occurrence_experience.build_personal_day_of_data", return_value={"identity": "personal_day_of"}),
        ):
            return resolve_occurrence_experience(
                occurrence=self.occurrence, viewer=self.viewer,
                surface=surface, observed_at=self.now,
            )

    def test_participant_and_operator_coexist_without_switch(self):
        participant = {
            "access": [{"status": "valid"}],
            "queue": [],
            "next_action": {
                "type": "checkpoint", "source": "operations.flow",
                "label": "Rejoindre la salle",
            },
        }
        operator = {
            "perspective": "operator", "queue": [], "capacity": [],
            "next_action": {
                "type": "readiness", "source": "operations.readiness",
                "label": "Préparer le contrôle",
            },
        }
        data = self._resolve(
            participant=participant, operator=operator,
            owner_operations=True, scanner=True,
        )
        self.assertEqual(set(data["sections"]), {"participant", "organizer"})
        self.assertEqual(data["relations"]["organizer"], True)
        self.assertEqual(data["relations"]["participant"], True)
        self.assertFalse(data["presentation"]["role_switch_required"])
        self.assertTrue(data["presentation"]["simultaneous_sections"])
        self.assertIn("scanner", data["capabilities"])
        self.assertIn("operations_view", data["capabilities"])
        self.assertIn("live", data["links"])
        self.assertEqual(
            [action["territory"] for action in data["actions"]],
            ["participant", "organizer", "organizer"],
        )

    def test_institutional_journey_is_shared_not_personal_access(self):
        institutional = [{
            "id": "shared",
            "status": "confirmed",
            "workflow": "service",
            "beneficiary": {"kind": "space", "id": "space"},
        }]
        data = self._resolve(institutional=institutional)
        self.assertEqual(set(data["sections"]), {"institutional"})
        self.assertEqual(len(data["sections"]["institutional"]), 1)
        self.assertTrue(data["relations"]["institutional_beneficiary"])
        self.assertFalse(data["relations"]["participant"])
        self.assertNotIn("participant", data["sections"])
        self.assertNotIn("present_credential", data["capabilities"])

    def test_scanner_without_operator_view_does_not_disclose_operations(self):
        operator = {"perspective": "operator", "queue": [{"label": "private"}]}
        data = self._resolve(operator=operator, scanner=True)
        self.assertNotIn("organizer", data["sections"])
        self.assertNotIn("platform", data["sections"])
        self.assertIn("scanner", data["capabilities"])
        # No operator facts may leak into knowledge without owner view authority.
        # A scanner can have scan permission without general operations view.
        self.assertFalse(data["relations"]["participant"])
        self.assertFalse(any(
            fact.get("domain") == "organizer"
            for fact in data["knowledge"]["facts"]
        ))

    def test_finance_logistics_and_scanner_permissions_are_cumulative(self):
        data = self._resolve(
            finance=True, scanner=True,
            extra_grants=(
                PermissionCode.ACTIVITY_CAPACITY_VIEW,
                PermissionCode.ACTIVITY_COMMERCE_MANAGE,
            ),
        )
        self.assertTrue(data["relations"]["organizer"])
        self.assertEqual(
            {"scanner", "finance_view", "capacity_view", "commerce_manage"}
            - set(data["capabilities"]),
            set(),
        )
        self.assertFalse(data["presentation"]["role_switch_required"])

    def test_platform_only_is_not_organizer(self):
        operator = {"perspective": "operator", "queue": []}
        data = self._resolve(operator=operator, platform=True)
        self.assertIn("platform", data["sections"])
        self.assertNotIn("organizer", data["sections"])
        self.assertTrue(data["relations"]["platform"])

    def test_anonymous_or_unauthorized_has_no_projection(self):
        self.viewer.is_authenticated = False
        self.assertIsNone(self._resolve())
        self.viewer.is_authenticated = True
        self.assertIsNone(self._resolve())

    def test_live_is_optional_even_when_the_day_of_exists(self):
        data = self._resolve(
            participant={"access": [{"status": "valid"}]},
            live_enabled=False,
        )
        self.assertIsNotNone(data)
        self.assertFalse(data["live"]["available"])
        self.assertNotIn("live", data["links"])
        self.assertIsNone(self._resolve(
            participant={"access": [{"status": "valid"}]},
            live_enabled=False, surface="live",
        ))

    def test_live_closed_after_occurrence(self):
        self.assertIsNone(self._resolve(
            participant={"access": []}, phase="after", surface="live",
        ))

    def test_live_phase_has_distinct_payload(self):
        participant = {"access": [{"status": "valid"}], "queue": []}
        data = self._resolve(participant=participant, surface="live")
        self.assertEqual(data["sections"]["participant"], participant)
        self.assertEqual(data["knowledge"]["coverage"]["state"], "PARTIAL")
        self.assertEqual(data["knowledge"]["planned_timing"]["truth"], "planned")


class OccurrenceLiveTruthTests(SimpleTestCase):
    def test_no_fake_observations_or_completed_coverage(self):
        now = timezone.now()
        occurrence = SimpleNamespace(
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=3),
            timezone="Africa/Kinshasa",
        )
        result = compose_live_knowledge(
            occurrence=occurrence, participant=None, operator=None,
            institutional=[], observed_at=now,
        )
        self.assertEqual(result["coverage"]["state"], "UNAVAILABLE")
        self.assertEqual(result["planned_timing"]["truth"], "planned")
        self.assertEqual(result["facts"], [])
        self.assertEqual(result["transitions"]["state"], "unavailable")
        self.assertEqual(result["media"]["state"], "unavailable")

    def test_queue_fact_does_not_invent_its_event_timestamp(self):
        now = timezone.now()
        occurrence = SimpleNamespace(start_at=None, end_at=None, timezone="UTC")
        result = compose_live_knowledge(
            occurrence=occurrence, operator=None, institutional=[],
            participant={"queue": [{"status": "waiting", "position": 2, "label": "Accueil"}]},
            observed_at=now,
        )
        self.assertEqual(result["coverage"]["state"], "PARTIAL")
        self.assertEqual(result["facts"][0]["truth"], "observed")
        self.assertIsNone(result["facts"][0]["occurred_at"])
        self.assertNotEqual(result["coverage"]["state"], "ESTABLISHED")

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.frontier import FrontierClaim
from prospector.observation_contracts import (
    ObservationTarget,
    observation_target_from_claim,
)
from research_missions.contracts import (
    ResearchFamily,
    ResearchMission,
    ResearchMissionCandidate,
    ResearchMissionContractError,
    ResearchOrigin,
    ResearchOriginKind,
)
from research_missions.prospecting import (
    ProspectingPlan,
    project_to_prospecting_mission,
)


class ResearchMissionContractTests(TestCase):
    def setUp(self):
        self.origin = ResearchOrigin(
            kind=ResearchOriginKind.REQUIREMENT,
            source_ref="requirement:scholarship-x:toefl",
            context={"predicate": "language_score"},
        )
        self.base = ResearchMission(
            primary_family=ResearchFamily.REQUIREMENT,
            subject="Bourse X",
            questions=("Quelles sont les conditions ?",),
            known_context={"country": "CD"},
            unknowns=("score TOEFL minimal",),
            origins=(self.origin,),
            reasons=("Une condition de langue reste inconnue",),
            priority=50,
            scope={"country": "CD"},
            limits={"max_depth": 2},
        )

    def test_exactly_eight_research_families_are_formalized(self):
        self.assertEqual(
            {value.value for value in ResearchFamily},
            {
                "POSSIBILITY",
                "REQUIREMENT",
                "QUALIFICATION",
                "ACTOR",
                "SPATIOTEMPORAL",
                "PROCEDURE",
                "ECONOMIC",
                "REFERENCE",
            },
        )

    def test_invalid_family_is_rejected(self):
        with self.assertRaises(ResearchMissionContractError):
            ResearchMission(
                primary_family="VISA",
                subject="Visa X",
                questions=("Quelles conditions ?",),
                origins=(self.origin,),
                reasons=("Question ouverte",),
            )

    def test_subject_questions_and_context_are_immutable(self):
        self.assertEqual(self.base.subject, "Bourse X")
        self.assertEqual(
            self.base.questions,
            ("Quelles sont les conditions ?",),
        )
        with self.assertRaises(FrozenInstanceError):
            self.base.subject = "Autre"
        with self.assertRaises(TypeError):
            self.base.known_context["country"] = "KE"

    def test_fingerprint_is_stable_across_provenance_and_formatting(self):
        other = ResearchMission(
            primary_family=ResearchFamily.REQUIREMENT,
            subject="  BOURSE   x ",
            questions=("quelles sont les CONDITIONS ?",),
            known_context={"country": "KE", "fresh": True},
            unknowns=("SCORE   toefl minimal",),
            origins=(
                ResearchOrigin(
                    kind=ResearchOriginKind.WATCH,
                    source_ref="watch:scholarships",
                ),
            ),
            reasons=("Une veille a révélé la même question",),
            priority=900,
            scope={"country": "CD"},
            limits={"max_depth": 9},
        )
        self.assertEqual(self.base.fingerprint, other.fingerprint)
        self.assertEqual(self.base.mission_ref, other.mission_ref)

    def test_fingerprint_changes_when_need_changes(self):
        changed_question = ResearchMission(
            primary_family=self.base.primary_family,
            subject=self.base.subject,
            questions=("Quelle est la date limite ?",),
            known_context=self.base.known_context,
            unknowns=self.base.unknowns,
            origins=self.base.origins,
            reasons=self.base.reasons,
            priority=self.base.priority,
            scope=self.base.scope,
            limits=self.base.limits,
        )
        changed_scope = ResearchMission(
            primary_family=self.base.primary_family,
            subject=self.base.subject,
            questions=self.base.questions,
            known_context=self.base.known_context,
            unknowns=self.base.unknowns,
            origins=self.base.origins,
            reasons=self.base.reasons,
            priority=self.base.priority,
            scope={"country": "KE"},
            limits=self.base.limits,
        )
        self.assertNotEqual(
            self.base.fingerprint,
            changed_question.fingerprint,
        )
        self.assertNotEqual(
            self.base.fingerprint,
            changed_scope.fingerprint,
        )

    def test_candidate_deduplicates_need_but_keeps_distinct_origin(self):
        first = ResearchMissionCandidate(
            primary_family=ResearchFamily.QUALIFICATION,
            subject="TOEFL",
            questions=(
                "Qu'est-ce qui constitue une preuve valide ?",
            ),
            origin=ResearchOrigin(
                kind=ResearchOriginKind.REQUIREMENT,
                source_ref="requirement:scholarship-a:toefl",
            ),
            reason="Bourse A exige TOEFL",
        )
        second = ResearchMissionCandidate(
            primary_family=ResearchFamily.QUALIFICATION,
            subject="toefl",
            questions=(
                "qu'est-ce qui constitue une preuve valide ?",
            ),
            origin=ResearchOrigin(
                kind=ResearchOriginKind.REQUIREMENT,
                source_ref="requirement:scholarship-b:toefl",
            ),
            reason="Bourse B exige TOEFL",
        )
        self.assertEqual(first.mission_ref, second.mission_ref)

        admitted = first.to_mission().with_provenance(
            origin=second.origin,
            reason=second.reason,
        )
        self.assertEqual(admitted.mission_ref, first.mission_ref)
        self.assertEqual(len(admitted.origins), 2)
        self.assertEqual(len(admitted.reasons), 2)

    def test_provenance_payload_round_trips_with_same_identity(self):
        rebuilt = ResearchMission.from_provenance_payload(
            self.base.to_provenance_payload()
        )
        self.assertEqual(rebuilt, self.base)
        self.assertEqual(rebuilt.mission_ref, self.base.mission_ref)


class ResearchMissionProjectionTests(TestCase):
    def _mission(self):
        return ResearchMission(
            primary_family=ResearchFamily.REQUIREMENT,
            subject="Bourse X",
            questions=("Quelles sont les conditions ?",),
            origins=(
                ResearchOrigin(
                    kind=ResearchOriginKind.INITIAL,
                    source_ref="seed:scholarship-x",
                ),
            ),
            reasons=("Comprendre l'éligibilité",),
        )

    def test_projection_keeps_prospecting_selectors_explicit_and_bounded(self):
        mission = self._mission()
        projected = project_to_prospecting_mission(
            mission,
            ProspectingPlan(
                host_tlds=("cd",),
                languages=("fr",),
                path_terms=("bourse", "admission"),
                max_candidates=120,
                context={"campaign_key": "scholarships"},
            ),
            issued_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        )
        self.assertEqual(projected.mission_key, mission.mission_ref)
        self.assertEqual(
            projected.path_terms,
            ("bourse", "admission"),
        )
        self.assertNotIn("requirement", projected.path_terms)
        self.assertEqual(projected.max_candidates, 120)
        snapshot = projected.context["research_mission"]
        self.assertEqual(
            snapshot["primary_family"],
            "REQUIREMENT",
        )
        self.assertEqual(
            snapshot["mission_ref"],
            mission.mission_ref,
        )

    def test_primary_family_is_not_an_actor3_output_filter(self):
        projected = project_to_prospecting_mission(
            self._mission(),
            ProspectingPlan(
                host_tlds=("org",),
                path_terms=("scholarship",),
            ),
            issued_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        )
        self.assertFalse(
            hasattr(projected, "allowed_result_families")
        )


class ResearchMissionObserverBoundaryTests(TestCase):
    def test_observation_target_does_not_receive_research_context(self):
        now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator="https://example.test/scholarship",
            kind="web_url",
            first_discovered_at=now,
            evidence=(
                ProspectingEvidence(
                    method="external_index",
                    discovered_at=now,
                ),
            ),
            policy_context={
                "mission_key": "research-mission:v1:test",
                "mission_context": {
                    "research_mission": {"subject": "Bourse X"}
                },
            },
            observation_hints={
                "indexed_mime_type": "text/html"
            },
        )
        claim = FrontierClaim(
            claim_token="claim-1",
            worker_id="worker-1",
            leased_until=now + timedelta(minutes=5),
            target=target,
            handoff_generation=1,
        )
        observation_target = observation_target_from_claim(
            claim,
            requested_at=now,
        )

        names = {item.name for item in fields(ObservationTarget)}
        self.assertNotIn("policy_context", names)
        self.assertNotIn("research_mission", names)
        self.assertEqual(
            observation_target.target_key,
            target.target_key,
        )
        self.assertEqual(
            observation_target.observation_hints,
            {"indexed_mime_type": "text/html"},
        )

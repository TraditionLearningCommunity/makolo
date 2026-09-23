from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone as django_timezone

from activities.models import Activity, Occurrence
from geography.models import Place
from interpreter.contracts import (
    CandidateEntity,
    CandidateFact,
    CandidateRelation,
    CandidateValue,
    InterpretedMaterial,
    InterpretationOutcome,
    LogicOperator,
    candidate_storage_payload,
)
from interpreter.django_app.models import InterpretationCandidate, InterpretationRun
from interpreter.identifiers import make_interpretation_ref
from observer.django_app.models import Observation, ObservationSeries, ObserverHandoff
from opportunities.models import Opportunity, OpportunitySource
from organizations.models import Organization
from prospector.canonicalization import canonicalize_locator
from prospector.django_app.models import ProspectorFeedbackEvent, ProspectorFrontierEntry

from resolver.contracts import (
    CanonicalRef,
    ResolutionAlternative,
    ResolutionMethod,
    ResolutionOutcome,
    ResolutionStatus,
    ResolutionStrength,
)
from resolver.django_catalog import DjangoRealityCatalog
from resolver.django_store import (
    DjangoResolvedMaterialSource,
    claim_resolutions,
    enqueue_resolutions,
    process_resolution_claim,
    recover_expired_resolutions,
)
from resolver.identifiers import strategy_fingerprint
from resolver.ports import EntityLookup, FactHistoryComparison
from resolver.strategy import DeterministicResolver, STRATEGY_COMPONENTS


def interpreted(*candidates, outcome=InterpretationOutcome.INTERPRETED, target_key=None, observation_ref="observer:observation:v1:test"):
    material_key = "observer:material:v2:test"
    fingerprint = "interpreter-test-fingerprint"
    ref = make_interpretation_ref(material_key=material_key, strategy_fingerprint=fingerprint)
    started = datetime(2026, 9, 23, 6, 0, tzinfo=timezone.utc)
    return InterpretedMaterial(
        interpretation_ref=ref,
        material_key=material_key,
        observation_ref=observation_ref,
        target_key=target_key or ("web_url:v1:" + "a" * 64),
        strategy_key="test",
        strategy_version="1",
        strategy_fingerprint=fingerprint,
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        outcome=outcome,
        candidates=tuple(candidates),
    )


class ExactCatalog:
    def lookup_entity(self, material, entity, context):
        return EntityLookup(
            families=("organization",),
            alternatives=(
                ResolutionAlternative(
                    CanonicalRef("organization", "org-1"),
                    ResolutionMethod.EXACT,
                    ResolutionStrength.EXACT,
                    ("official_external_identifier",),
                    "snapshot-1",
                ),
            ),
        )


class EmptyCatalog:
    def lookup_entity(self, material, entity, context):
        return EntityLookup(
            families=tuple(context["families"]),
            alternatives=(),
            provisional_identity_key=f"{material.target_key}:{entity.label}",
        )


class PossibleCatalog:
    def lookup_entity(self, material, entity, context):
        return EntityLookup(
            families=("organization",),
            alternatives=(
                ResolutionAlternative(
                    CanonicalRef("organization", "org-1"),
                    ResolutionMethod.HEURISTIC,
                    ResolutionStrength.POSSIBLE,
                    ("name_only_insufficient",),
                    "snapshot-1",
                ),
            ),
        )


class NoHistory:
    def compare_fact(self, **kwargs):
        return FactHistoryComparison()


class UpdateHistory:
    def compare_fact(self, **kwargs):
        return FactHistoryComparison(
            status="update",
            related_candidate_refs=("old-fact",),
            basis_codes=("same_source_later_observation",),
        )


class ResolverContractTests(SimpleTestCase):
    def resolve(self, material, catalog=None, history=None):
        now = datetime(2026, 9, 23, 6, 10, tzinfo=timezone.utc)
        return DeterministicResolver().resolve(
            material,
            catalog or EmptyCatalog(),
            history or NoHistory(),
            started_at=now,
            clock=lambda: now + timedelta(milliseconds=5),
        )

    def test_exact_identity_is_a_match_not_a_domain_mutation(self):
        entity = CandidateEntity("entity-1", "Université de Lubumbashi", ("organization",))
        result, stats = self.resolve(interpreted(entity), ExactCatalog())
        self.assertEqual(result.outcome, ResolutionOutcome.RESOLVED)
        resolution = result.entity_resolutions[0]
        self.assertEqual(resolution.status, ResolutionStatus.MATCHED)
        self.assertEqual(resolution.canonical_ref, CanonicalRef("organization", "org-1"))
        self.assertEqual(stats["matched_count"], 1)

    def test_no_safe_match_is_new_candidate_with_stable_provisional_identity(self):
        entity = CandidateEntity("entity-1", "Nouvelle réalité", ("organization",))
        first, _ = self.resolve(interpreted(entity))
        second, _ = self.resolve(interpreted(entity))
        left = first.entity_resolutions[0]
        right = second.entity_resolutions[0]
        self.assertEqual(left.status, ResolutionStatus.NEW_CANDIDATE)
        self.assertEqual(left.provisional_ref, right.provisional_ref)
        self.assertIsNone(left.canonical_ref)

    def test_one_weak_name_match_is_still_ambiguous(self):
        entity = CandidateEntity("entity-1", "UL", ("organization",))
        result, _ = self.resolve(interpreted(entity), PossibleCatalog())
        self.assertEqual(result.outcome, ResolutionOutcome.AMBIGUOUS)
        self.assertEqual(result.entity_resolutions[0].status, ResolutionStatus.AMBIGUOUS)


    def test_short_acronym_without_alias_evidence_stays_unresolved(self):
        entity = CandidateEntity("entity-1", "UL", ("organization",))
        result, _ = self.resolve(interpreted(entity), EmptyCatalog())
        self.assertEqual(result.outcome, ResolutionOutcome.UNRESOLVED)
        resolution = result.entity_resolutions[0]
        self.assertEqual(resolution.status, ResolutionStatus.UNRESOLVED)
        self.assertIsNone(resolution.provisional_ref)
        self.assertIn("short_alias_without_evidence", resolution.basis_codes)

    def test_relation_keeps_logic_modality_and_partial_endpoint(self):
        a = CandidateEntity("entity-a", "Offer X", ("employment",))
        b = CandidateEntity("entity-b", "CCNA", ("requirement_subject",))
        relation = CandidateRelation(
            "relation-1",
            "entity-a",
            "requires",
            "entity-b",
            logic_group="group-1",
            logic_operator=LogicOperator.OR,
        )
        result, _ = self.resolve(interpreted(a, b, relation))
        assertion = result.relation_resolutions[0]
        self.assertEqual(assertion.status, ResolutionStatus.LINKED)
        self.assertEqual(assertion.candidate_payload["logic_operator"], "or")
        self.assertEqual(assertion.candidate_payload["logic_group"], "group-1")

    def test_same_material_conflicting_deadlines_are_not_silently_chosen(self):
        entity = CandidateEntity("entity-1", "Offer X", ("employment",))
        a = CandidateFact(
            "fact-a",
            "deadline",
            CandidateValue(kind="date", raw_text="2026-10-10", date_value=date(2026, 10, 10)),
            subject_ref="entity-1",
        )
        b = CandidateFact(
            "fact-b",
            "deadline",
            CandidateValue(kind="date", raw_text="2026-10-15", date_value=date(2026, 10, 15)),
            subject_ref="entity-1",
        )
        result, _ = self.resolve(interpreted(entity, a, b))
        self.assertEqual(result.outcome, ResolutionOutcome.CONFLICT)
        self.assertTrue(any(item.status is ResolutionStatus.CONFLICT for item in result.fact_resolutions))
        self.assertTrue(result.conflicts)

    def test_same_source_later_fact_is_labelled_update_not_truth_replacement(self):
        entity = CandidateEntity("entity-1", "Offer X", ("employment",))
        fact = CandidateFact(
            "fact-a",
            "deadline",
            CandidateValue(kind="date", raw_text="2026-10-15", date_value=date(2026, 10, 15)),
            subject_ref="entity-1",
        )
        result, _ = self.resolve(interpreted(entity, fact), history=UpdateHistory())
        assertion = result.fact_resolutions[0]
        self.assertEqual(assertion.status, ResolutionStatus.UPDATE)
        self.assertIn("same_source_later_observation", assertion.basis_codes)
        self.assertEqual(assertion.related_candidate_refs, ("old-fact",))

    def test_partial_interpretation_cannot_be_promoted_to_fully_resolved(self):
        entity = CandidateEntity("entity-1", "Offer X", ("employment",))
        result, _ = self.resolve(interpreted(entity, outcome=InterpretationOutcome.PARTIAL))
        self.assertEqual(result.outcome, ResolutionOutcome.PARTIAL)
        self.assertIn("upstream_partial", result.warning_codes)


class ResolverDjangoCatalogTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="resolver-owner",
            email="resolver-owner@example.test",
            password="test-pass",
        )

    def observation(self, url, suffix):
        target_key = "web_url:v1:" + suffix * 64
        series = ObservationSeries.objects.create(
            target_key=target_key,
            kind="web_url",
            locator=url,
            profile_key="public-http",
            profile_fingerprint=f"profile-{suffix}",
        )
        handoff = ObserverHandoff.objects.create(
            handoff_key="observation:v1:" + suffix * 64,
            target_key=target_key,
            handoff_generation=1,
            locator=url,
            kind="web_url",
            requested_at=django_timezone.now(),
            contract_version=1,
            observation_hints={},
            absorbed_at=django_timezone.now(),
        )
        now = django_timezone.now()
        observation = Observation.objects.create(
            series=series,
            source_handoff=handoff,
            trigger="handoff",
            lifecycle="finalized",
            outcome="observed",
            started_at=now,
            observed_at=now + timedelta(seconds=1),
            completed_at=now + timedelta(seconds=2),
            requested_locator=url,
            final_locator=url,
            response_status=200,
            profile_ref="public-http",
            profile_fingerprint=f"profile-{suffix}",
            policy_fingerprint="policy-v1",
        )
        return target_key, observation.observation_ref

    def test_known_opportunity_source_url_is_exact(self):
        opportunity = Opportunity.objects.create(kind="job", created_by=self.user)
        OpportunitySource.objects.create(
            opportunity=opportunity,
            source_type="official",
            source_name="Company X",
            url="https://jobs.example.test/jobs/ABC123",
            external_reference="ABC123",
            is_primary=True,
        )
        target, observation_ref = self.observation("https://jobs.example.test/jobs/ABC123", "b")
        entity = CandidateEntity("entity-1", "Network Engineer", ("employment",))
        material = interpreted(entity, target_key=target, observation_ref=observation_ref)
        lookup = DjangoRealityCatalog().lookup_entity(
            material,
            entity,
            {"families": ("opportunity",), "facts": (), "all_candidates": material.candidates},
        )
        exact = [item for item in lookup.alternatives if item.strength is ResolutionStrength.EXACT]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].canonical_ref, CanonicalRef("opportunity", str(opportunity.pk)))
        self.assertIn("known_opportunity_source_url", exact[0].basis_codes)

    def test_same_organization_name_alone_never_auto_merges(self):
        Organization.objects.create(name="Université Alpha", created_by=self.user)
        entity = CandidateEntity("entity-1", "Université Alpha", ("organization",))
        material = interpreted(entity)
        lookup = DjangoRealityCatalog().lookup_entity(
            material,
            entity,
            {"families": ("organization",), "facts": (), "all_candidates": material.candidates},
        )
        self.assertEqual(len(lookup.alternatives), 1)
        self.assertEqual(lookup.alternatives[0].strength, ResolutionStrength.POSSIBLE)

    def test_same_activity_title_and_date_can_resolve_occurrence_not_activity(self):
        activity = Activity.objects.create(owner_profile=self.user, created_by=self.user, title="TOEFL Test")
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_date=date(2026, 10, 14),
            timing_kind="date_only",
            timezone="Africa/Lubumbashi",
            status="scheduled",
        )
        entity = CandidateEntity("entity-1", "TOEFL Test", ("assessment",))
        fact = CandidateFact(
            "fact-1",
            "start_date",
            CandidateValue(kind="date", raw_text="2026-10-14", date_value=date(2026, 10, 14)),
            subject_ref="entity-1",
        )
        material = interpreted(entity, fact)
        result, _ = DeterministicResolver().resolve(
            material,
            DjangoRealityCatalog(),
            NoHistory(),
            started_at=django_timezone.now(),
            clock=django_timezone.now,
        )
        resolved = result.entity_resolutions[0]
        self.assertEqual(resolved.status, ResolutionStatus.MATCHED)
        self.assertEqual(resolved.canonical_ref, CanonicalRef("occurrence", str(occurrence.pk)))

    def test_two_places_with_same_name_remain_ambiguous(self):
        Place.objects.create(name="Kasenga")
        Place.objects.create(name="Kasenga")
        entity = CandidateEntity("entity-1", "Kasenga", ("place",))
        material = interpreted(entity)
        result, _ = DeterministicResolver().resolve(
            material,
            DjangoRealityCatalog(),
            NoHistory(),
            started_at=django_timezone.now(),
            clock=django_timezone.now,
        )
        self.assertEqual(result.entity_resolutions[0].status, ResolutionStatus.AMBIGUOUS)


    def test_external_identifier_is_scoped_to_source_namespace(self):
        opportunity = Opportunity.objects.create(kind="job", created_by=self.user)
        OpportunitySource.objects.create(
            opportunity=opportunity,
            source_type="official",
            source_name="Company X",
            url="https://jobs.example.test/jobs/ABC123",
            external_reference="ABC123",
            is_primary=True,
        )
        target, observation_ref = self.observation("https://jobs.example.test/search", "m")
        entity = CandidateEntity("entity-1", "Network Engineer", ("employment",))
        external = CandidateFact(
            "fact-external",
            "external_reference",
            CandidateValue(kind="text", raw_text="ABC123", text="ABC123"),
            subject_ref="entity-1",
        )
        material = interpreted(entity, external, target_key=target, observation_ref=observation_ref)
        lookup = DjangoRealityCatalog().lookup_entity(
            material,
            entity,
            {"families": ("opportunity",), "facts": (external,), "all_candidates": material.candidates},
        )
        exact = [item for item in lookup.alternatives if "scoped_external_identifier" in item.basis_codes]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].canonical_ref, CanonicalRef("opportunity", str(opportunity.pk)))


class ResolverPersistenceTests(TestCase):
    def create_interpretation(self, *, label="Reality X", suffix="c", strategy="interpreter-v1", target_key=None):
        material_key = f"observer:material:v2:{suffix}"
        interpretation_ref = make_interpretation_ref(
            material_key=material_key,
            strategy_fingerprint=strategy,
        )
        now = django_timezone.now()
        run = InterpretationRun.objects.create(
            interpretation_ref=interpretation_ref,
            observation_ref=f"observer:observation:v1:{suffix}",
            material_key=material_key,
            target_key=target_key or ("web_url:v1:" + suffix * 64),
            strategy_key="test",
            strategy_version="1",
            strategy_fingerprint=strategy,
            lifecycle="finalized",
            outcome="interpreted",
            started_at=now,
            completed_at=now + timedelta(seconds=1),
        )
        candidate = CandidateEntity(f"candidate-{suffix}", label, ())
        InterpretationCandidate.objects.create(
            run=run,
            candidate_ref=candidate.candidate_ref,
            ordinal=1,
            kind="entity",
            payload=candidate_storage_payload(candidate),
        )
        return run

    def test_enqueue_claim_finalize_project_is_idempotent(self):
        source = self.create_interpretation()
        self.assertEqual(enqueue_resolutions(limit=10), 1)
        self.assertEqual(enqueue_resolutions(limit=10), 0)
        claim = claim_resolutions(worker_id="resolver-test", limit=1)[0]
        run = process_resolution_claim(
            claim,
            catalog=EmptyCatalog(),
            history=NoHistory(),
        )
        self.assertEqual(run.lifecycle, "finalized")
        projected = DjangoResolvedMaterialSource().get_material(run.resolution_ref)
        self.assertEqual(projected.interpretation_ref, source.interpretation_ref)
        self.assertEqual(projected.entity_resolutions[0].status, ResolutionStatus.NEW_CANDIDATE)
        self.assertEqual(enqueue_resolutions(limit=10), 0)

    def test_new_resolver_strategy_preserves_old_history(self):
        source = self.create_interpretation(suffix="d")
        enqueue_resolutions()
        first = process_resolution_claim(
            claim_resolutions(worker_id="v1", limit=1)[0],
            catalog=EmptyCatalog(),
            history=NoHistory(),
        )

        class StrategyV2(DeterministicResolver):
            strategy_version = "2.0"
            strategy_fingerprint = strategy_fingerprint({**STRATEGY_COMPONENTS, "family_routing": "2"})

        v2 = StrategyV2()
        self.assertEqual(enqueue_resolutions(strategy=v2), 1)
        second = process_resolution_claim(
            claim_resolutions(worker_id="v2", limit=1)[0],
            strategy=v2,
            catalog=EmptyCatalog(),
            history=NoHistory(),
        )
        self.assertNotEqual(first.resolution_ref, second.resolution_ref)
        self.assertEqual(
            source.resolutionrun_set.count() if hasattr(source, "resolutionrun_set") else 0,
            0,
        )
        from resolver.django_app.models import ResolutionRun
        self.assertEqual(ResolutionRun.objects.filter(interpretation_ref=source.interpretation_ref).count(), 2)

    def test_expired_lease_recovers(self):
        self.create_interpretation(suffix="e")
        enqueue_resolutions()
        claim = claim_resolutions(worker_id="dead", limit=1, lease_seconds=300)[0]
        from resolver.django_app.models import ResolutionRun
        ResolutionRun.objects.filter(resolution_ref=claim.resolution_ref).update(
            lease_expires_at=django_timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(recover_expired_resolutions(now=django_timezone.now()), 1)
        run = ResolutionRun.objects.get(resolution_ref=claim.resolution_ref)
        self.assertEqual(run.lifecycle, "pending")
        self.assertIsNone(run.claim_token)

    def test_resolver_does_not_create_or_mutate_owner_domains(self):
        self.create_interpretation(suffix="f")
        before = {
            "activities": Activity.objects.count(),
            "occurrences": Occurrence.objects.count(),
            "organizations": Organization.objects.count(),
            "places": Place.objects.count(),
            "opportunities": Opportunity.objects.count(),
        }
        enqueue_resolutions()
        process_resolution_claim(
            claim_resolutions(worker_id="no-mutation", limit=1)[0],
            catalog=EmptyCatalog(),
            history=NoHistory(),
        )
        after = {
            "activities": Activity.objects.count(),
            "occurrences": Occurrence.objects.count(),
            "organizations": Organization.objects.count(),
            "places": Place.objects.count(),
            "opportunities": Opportunity.objects.count(),
        }
        self.assertEqual(before, after)


    def test_two_workers_claim_disjoint_runs(self):
        self.create_interpretation(suffix="g")
        self.create_interpretation(suffix="h")
        self.assertEqual(enqueue_resolutions(limit=10), 2)
        first = claim_resolutions(worker_id="worker-a", limit=1)[0]
        second = claim_resolutions(worker_id="worker-b", limit=1)[0]
        self.assertNotEqual(first.resolution_ref, second.resolution_ref)

    def test_same_source_same_label_converges_to_same_provisional_identity(self):
        target = "web_url:v1:" + "i" * 64
        self.create_interpretation(suffix="i", label="Same Reality", target_key=target)
        self.create_interpretation(suffix="j", label="Same Reality", strategy="interpreter-v2", target_key=target)
        enqueue_resolutions(limit=10)
        provisional = []
        for worker in ("one", "two"):
            claim = claim_resolutions(worker_id=worker, limit=1)[0]
            run = process_resolution_claim(claim, catalog=EmptyCatalog(), history=NoHistory())
            provisional.append(
                DjangoResolvedMaterialSource().get_material(run.resolution_ref).entity_resolutions[0].provisional_ref
            )
        self.assertEqual(provisional[0], provisional[1])

    def test_stale_canonical_snapshot_requeues_before_finalization(self):
        self.create_interpretation(suffix="k")
        enqueue_resolutions()

        class StaleCatalog(ExactCatalog):
            def validate_output(self, output):
                return False

        claim = claim_resolutions(worker_id="stale", limit=1)[0]
        run = process_resolution_claim(claim, catalog=StaleCatalog(), history=NoHistory())
        self.assertEqual(run.lifecycle, "pending")
        self.assertEqual(run.stats["stale_candidate_retries"], 1)
        self.assertIn("canonical_changed_during_resolution", run.warning_codes)

    def test_reality_new_feedback_reuses_prospector_contract_without_business_payload(self):
        target = canonicalize_locator(kind="web_url", locator="https://example.test/reality")
        source = self.create_interpretation(suffix="l", target_key=target.target_key)
        now = django_timezone.now()
        ProspectorFrontierEntry.objects.create(
            target_key=target.target_key,
            kind=target.kind,
            locator=target.locator,
            status="ready",
            priority=100,
            available_at=now,
            first_discovered_at=now,
            last_discovered_at=now,
            discovery_count=1,
            handoff_generation=1,
            policy_context={},
            observation_hints={},
        )
        enqueue_resolutions()
        run = process_resolution_claim(
            claim_resolutions(worker_id="feedback", limit=1)[0],
            catalog=EmptyCatalog(),
            history=NoHistory(),
        )
        event = ProspectorFeedbackEvent.objects.get(
            producer="resolver",
            source_ref=run.resolution_ref,
            signal="reality_new",
        )
        self.assertEqual(event.target_key, source.target_key)
        self.assertFalse(hasattr(event, "payload"))

from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import (
    ProspectorFrontierEntry,
    ProspectorFrontierEvidence,
)
from prospector.django_frontier import DjangoFrontierStore
from prospector.expansion import ExpansionPolicy, ObservationExpansionSink
from prospector.observation_contracts import (
    ObservationReport,
    ObservationStatus,
    ObservedReference,
    make_handoff_key,
)


class DjangoObservationExpansionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        self.store = DjangoFrontierStore()
        self.parent = self.store.admit_sync(
            ProspectingCandidate(
                locator="https://example.test/root",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                        provider="test-index",
                    ),
                ),
                policy_context={
                    "mission_key": "rdc",
                    "campaign_key": "skills",
                    "branch_key": "root",
                    "depth": 0,
                },
            )
        )
        self.policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=20,
            max_candidates_per_report=10,
            max_same_host_candidates=6,
            max_cross_host_candidates=4,
            max_unique_cross_hosts=3,
            max_per_host_candidates=4,
            max_per_url_shape=3,
            max_query_parameters=4,
            max_path_segments=8,
        )

    def report(self):
        return ObservationReport(
            handoff_key=make_handoff_key(
                target_key=self.parent.target_key,
                handoff_generation=1,
            ),
            target_key=self.parent.target_key,
            handoff_generation=1,
            observation_ref="obs:postgres:1",
            status=ObservationStatus.OBSERVED,
            observed_at=self.now,
            requested_locator=self.parent.locator,
            final_locator=self.parent.locator,
            response_status=200,
            media_type="text/html",
            references=(
                ObservedReference(
                    relation="link",
                    locator="https://example.test/programs/ccna",
                    discovered_at=self.now,
                    attributes={
                        "media_type": "text/html",
                        "title": "must not be persisted as evidence",
                    },
                ),
            ),
        )

    def test_expansion_persists_bounded_edge_provenance_in_existing_frontier(self):
        sink = ObservationExpansionSink(
            frontier=self.store,
            lookup=self.store,
            policy=self.policy,
        )
        result = async_to_sync(sink.submit_report)(self.report())

        self.assertEqual(result.admitted, 1)
        self.assertEqual(ProspectorFrontierEntry.objects.count(), 2)

        child = ProspectorFrontierEntry.objects.exclude(
            target_key=self.parent.target_key
        ).get()
        self.assertEqual(child.policy_context["mission_key"], "rdc")
        self.assertEqual(child.policy_context["campaign_key"], "skills")
        self.assertEqual(child.policy_context["branch_key"], "root")
        self.assertEqual(child.policy_context["depth"], 1)

        evidence = ProspectorFrontierEvidence.objects.get(frontier_entry=child)
        self.assertEqual(evidence.method, "web_graph")
        self.assertEqual(evidence.source_target_key, self.parent.target_key)
        self.assertEqual(evidence.source_observation_ref, "obs:postgres:1")
        self.assertEqual(evidence.attributes["relation"], "link")
        self.assertEqual(evidence.attributes["media_type"], "text/html")
        self.assertNotIn("title", evidence.attributes)

    def test_replayed_report_does_not_create_duplicate_target_or_edge_row(self):
        sink = ObservationExpansionSink(
            frontier=self.store,
            lookup=self.store,
            policy=self.policy,
        )
        report = self.report()
        async_to_sync(sink.submit_report)(report)
        async_to_sync(sink.submit_report)(report)

        self.assertEqual(ProspectorFrontierEntry.objects.count(), 2)
        child = ProspectorFrontierEntry.objects.exclude(
            target_key=self.parent.target_key
        ).get()
        self.assertEqual(
            ProspectorFrontierEvidence.objects.filter(
                frontier_entry=child,
                source_observation_ref="obs:postgres:1",
            ).count(),
            1,
        )

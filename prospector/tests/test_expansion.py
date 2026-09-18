from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.canonicalization import canonicalize_locator
from prospector.contracts import (
    ProspectingEvidence,
    ProspectingTarget,
)
from prospector.errors import ExpansionContractError
from prospector.expansion import ExpansionPolicy, ObservationExpansionSink
from prospector.observation_contracts import (
    ObservationReport,
    ObservationStatus,
    ObservedReference,
    make_handoff_key,
)


class FakeFrontier:
    def __init__(self, parent):
        self.targets = {parent.target_key: parent}
        self.candidates = []

    async def get(self, target_key):
        return self.targets.get(target_key)

    async def admit(self, candidate):
        self.candidates.append(candidate)
        from prospector.canonicalization import canonicalize_locator

        canonical = canonicalize_locator(kind=candidate.kind, locator=candidate.locator)
        target = ProspectingTarget(
            target_key=canonical.target_key,
            locator=canonical.locator,
            kind=canonical.kind,
            first_discovered_at=min(e.discovered_at for e in candidate.evidence),
            evidence=candidate.evidence,
            policy_context=candidate.policy_context,
            observation_hints=candidate.observation_hints,
        )
        self.targets[target.target_key] = target
        return target


class ExpansionTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now,
            provider="test",
        )
        parent_locator = "https://example.test/root"
        parent_canonical = canonicalize_locator(
            kind="web_url",
            locator=parent_locator,
        )
        self.parent = ProspectingTarget(
            target_key=parent_canonical.target_key,
            locator=parent_canonical.locator,
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(evidence,),
            policy_context={
                "mission_key": "rdc",
                "campaign_key": "skills",
                "branch_key": "root-a",
                "depth": 2,
            },
        )
        self.frontier = FakeFrontier(self.parent)
        self.policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=20,
            max_candidates_per_report=10,
            max_same_host_candidates=6,
            max_cross_host_candidates=4,
            max_unique_cross_hosts=3,
            max_per_host_candidates=4,
            max_per_url_shape=2,
            max_query_parameters=4,
            max_path_segments=8,
        )

    def report(self, references=(), *, final_locator=None, status=ObservationStatus.OBSERVED):
        return ObservationReport(
            handoff_key=make_handoff_key(
                target_key=self.parent.target_key,
                handoff_generation=1,
            ),
            target_key=self.parent.target_key,
            handoff_generation=1,
            observation_ref="obs:test:1",
            status=status,
            observed_at=self.now,
            requested_locator=self.parent.locator,
            final_locator=final_locator,
            response_status=200 if status is ObservationStatus.OBSERVED else None,
            media_type="text/html" if status is ObservationStatus.OBSERVED else None,
            references=tuple(references),
            failure_code="observer.failed" if status is ObservationStatus.FAILED else None,
        )

    async def expand(self, report):
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=self.policy,
        )
        return await sink.submit_report(report)

    async def test_expansion_kill_switch_does_not_touch_frontier(self):
        policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=10,
            max_candidates_per_report=10,
            max_same_host_candidates=10,
            max_cross_host_candidates=10,
            max_unique_cross_hosts=10,
            max_per_host_candidates=10,
            max_per_url_shape=10,
            max_query_parameters=4,
            max_path_segments=8,
            enabled=False,
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=policy,
        )
        report = self.report(
            (
                ObservedReference(
                    "link",
                    "https://example.test/child",
                    self.now,
                ),
            )
        )
        result = await sink.submit_report(report)
        self.assertEqual(result.admitted, 0)
        self.assertEqual(result.skip_counts["expansion_disabled"], 1)
        self.assertEqual(self.frontier.candidates, [])

    async def test_zero_cross_host_and_zero_query_are_valid_hard_limits(self):
        policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=10,
            max_candidates_per_report=10,
            max_same_host_candidates=10,
            max_cross_host_candidates=0,
            max_unique_cross_hosts=0,
            max_per_host_candidates=10,
            max_per_url_shape=10,
            max_query_parameters=0,
            max_path_segments=8,
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=policy,
        )
        refs = (
            ObservedReference("link", "https://other.test/a", self.now),
            ObservedReference("link", "https://example.test/a?x=1", self.now),
            ObservedReference("link", "https://example.test/b", self.now),
        )
        result = await sink.submit_report(self.report(refs))
        self.assertEqual(result.admitted, 1)
        self.assertEqual(result.skip_counts["cross_host_limit"], 1)
        self.assertEqual(result.skip_counts["query_parameter_limit"], 1)

    async def test_web_sitemap_and_feed_relations_become_candidates(self):
        result = await self.expand(
            self.report(
                (
                    ObservedReference(
                        relation="link",
                        locator="https://example.test/jobs",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="sitemap",
                        locator="https://example.test/sitemap.xml",
                        discovered_at=self.now,
                        attributes={"media_type": "application/xml"},
                    ),
                    ObservedReference(
                        relation="feed",
                        locator="https://feeds.example.test/jobs.xml",
                        discovered_at=self.now,
                    ),
                )
            )
        )

        self.assertEqual(result.admitted, 3)
        methods = [item.evidence[0].method for item in self.frontier.candidates]
        self.assertEqual(methods, ["web_graph", "sitemap", "feed"])
        for candidate in self.frontier.candidates:
            self.assertEqual(candidate.policy_context["mission_key"], "rdc")
            self.assertEqual(candidate.policy_context["campaign_key"], "skills")
            self.assertEqual(candidate.policy_context["depth"], 3)
            evidence = candidate.evidence[0]
            self.assertEqual(evidence.source_target_key, self.parent.target_key)
            self.assertEqual(evidence.source_observation_ref, "obs:test:1")

    async def test_sitemap_and_feed_entries_expand_without_parsing_content_here(self):
        await self.expand(
            self.report(
                (
                    ObservedReference(
                        relation="sitemap_entry",
                        locator="https://example.test/programs/1",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="feed_entry",
                        locator="https://example.test/news/1",
                        discovered_at=self.now,
                    ),
                )
            )
        )
        self.assertEqual(
            [c.evidence[0].method for c in self.frontier.candidates],
            ["sitemap", "feed"],
        )

    async def test_redirect_final_is_a_structural_candidate(self):
        result = await self.expand(
            self.report(final_locator="https://example.test/final")
        )
        self.assertEqual(result.admitted, 1)
        self.assertEqual(
            self.frontier.candidates[0].evidence[0].attributes["relation"],
            "redirect_final",
        )

    async def test_duplicate_self_unknown_and_invalid_references_are_bounded(self):
        result = await self.expand(
            self.report(
                (
                    ObservedReference(
                        relation="link",
                        locator="https://example.test/root#self",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="link",
                        locator="https://example.test/child",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="link",
                        locator="https://EXAMPLE.test:443/child#dup",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="semantic_requirement",
                        locator="https://example.test/not-ours",
                        discovered_at=self.now,
                    ),
                    ObservedReference(
                        relation="link",
                        locator="mailto:test@example.test",
                        discovered_at=self.now,
                    ),
                )
            )
        )
        self.assertEqual(result.admitted, 1)
        self.assertEqual(result.skip_counts["self_reference"], 1)
        self.assertEqual(result.skip_counts["duplicate_reference"], 1)
        self.assertEqual(result.skip_counts["unknown_relation"], 1)
        self.assertEqual(result.skip_counts["invalid_locator"], 1)

    async def test_shape_limit_stops_calendar_and_pagination_explosion(self):
        references = tuple(
            ObservedReference(
                relation="link",
                locator=f"https://example.test/calendar/2026-09-{day:02d}?page={day}",
                discovered_at=self.now,
            )
            for day in range(1, 7)
        )
        result = await self.expand(self.report(references))
        self.assertEqual(result.admitted, 2)
        self.assertEqual(result.skip_counts["url_shape_limit"], 4)

    async def test_same_cross_host_and_unique_host_limits_are_enforced(self):
        policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=20,
            max_candidates_per_report=20,
            max_same_host_candidates=1,
            max_cross_host_candidates=3,
            max_unique_cross_hosts=2,
            max_per_host_candidates=5,
            max_per_url_shape=5,
            max_query_parameters=4,
            max_path_segments=8,
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=policy,
        )
        refs = (
            ObservedReference("link", "https://example.test/a", self.now),
            ObservedReference("link", "https://example.test/b", self.now),
            ObservedReference("link", "https://one.test/a", self.now),
            ObservedReference("link", "https://two.test/a", self.now),
            ObservedReference("link", "https://three.test/a", self.now),
        )
        result = await sink.submit_report(self.report(refs))
        self.assertEqual(result.admitted, 3)
        self.assertEqual(result.skip_counts["same_host_limit"], 1)
        self.assertEqual(result.skip_counts["unique_cross_host_limit"], 1)

    async def test_sensitive_query_is_rejected_before_frontier_admission(self):
        result = await self.expand(
            self.report(
                (
                    ObservedReference(
                        relation="link",
                        locator="https://example.test/private?access_token=secret",
                        discovered_at=self.now,
                    ),
                )
            )
        )
        self.assertEqual(result.admitted, 0)
        self.assertEqual(result.skip_counts["sensitive_query"], 1)
        self.assertEqual(self.frontier.candidates, [])

    async def test_query_and_path_limits_are_enforced(self):
        policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=10,
            max_candidates_per_report=10,
            max_same_host_candidates=10,
            max_cross_host_candidates=10,
            max_unique_cross_hosts=10,
            max_per_host_candidates=10,
            max_per_url_shape=10,
            max_query_parameters=1,
            max_path_segments=2,
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=policy,
        )
        refs = (
            ObservedReference("link", "https://example.test/a?x=1&y=2", self.now),
            ObservedReference("link", "https://example.test/a/b/c", self.now),
        )
        result = await sink.submit_report(self.report(refs))
        self.assertEqual(result.admitted, 0)
        self.assertEqual(result.skip_counts["query_parameter_limit"], 1)
        self.assertEqual(result.skip_counts["path_segment_limit"], 1)

    async def test_query_path_depth_and_report_caps_fail_closed(self):
        shallow_policy = ExpansionPolicy(
            max_depth=2,
            max_references_per_report=2,
            max_candidates_per_report=2,
            max_same_host_candidates=2,
            max_cross_host_candidates=2,
            max_unique_cross_hosts=2,
            max_per_host_candidates=2,
            max_per_url_shape=2,
            max_query_parameters=1,
            max_path_segments=2,
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=shallow_policy,
        )
        refs = (
            ObservedReference("link", "https://example.test/a?x=1&y=2", self.now),
            ObservedReference("link", "https://example.test/a/b/c", self.now),
            ObservedReference("link", "https://example.test/third", self.now),
        )
        result = await sink.submit_report(self.report(refs))
        self.assertEqual(result.admitted, 0)
        self.assertEqual(result.skip_counts["depth_exceeded"], 2)
        self.assertEqual(result.truncated_references, 1)

    async def test_non_observed_report_does_not_expand(self):
        result = await self.expand(
            self.report((), status=ObservationStatus.FAILED)
        )
        self.assertEqual(result.admitted, 0)
        self.assertEqual(self.frontier.candidates, [])

    async def test_reference_attributes_are_minimally_whitelisted(self):
        await self.expand(
            self.report(
                (
                    ObservedReference(
                        relation="link",
                        locator="https://example.test/child",
                        discovered_at=self.now,
                        attributes={
                            "media_type": "text/html",
                            "hreflang": "fr",
                            "secret": "must-not-propagate",
                            "title": "semantic-looking text",
                            "rel": {"not": "a scalar"},
                        },
                    ),
                )
            )
        )
        attrs = self.frontier.candidates[0].evidence[0].attributes
        self.assertEqual(attrs["media_type"], "text/html")
        self.assertEqual(attrs["hreflang"], "fr")
        self.assertNotIn("secret", attrs)
        self.assertNotIn("title", attrs)
        self.assertNotIn("rel", attrs)

    async def test_disabled_family_and_candidate_budget_are_enforced(self):
        policy = ExpansionPolicy(
            max_depth=4,
            max_references_per_report=10,
            max_candidates_per_report=1,
            max_same_host_candidates=10,
            max_cross_host_candidates=10,
            max_unique_cross_hosts=10,
            max_per_host_candidates=10,
            max_per_url_shape=10,
            max_query_parameters=4,
            max_path_segments=8,
            allowed_families=("web_graph",),
        )
        sink = ObservationExpansionSink(
            frontier=self.frontier,
            lookup=self.frontier,
            policy=policy,
        )
        refs = (
            ObservedReference("sitemap", "https://example.test/sitemap.xml", self.now),
            ObservedReference("link", "https://example.test/a", self.now),
            ObservedReference("link", "https://example.test/b", self.now),
        )
        result = await sink.submit_report(self.report(refs))
        self.assertEqual(result.admitted, 1)
        self.assertEqual(result.skip_counts["family_disabled"], 1)
        self.assertEqual(result.skip_counts["candidate_budget"], 1)

    async def test_missing_parent_fails_instead_of_inventing_context(self):
        self.frontier.targets.clear()
        with self.assertRaises(ExpansionContractError):
            await self.expand(self.report(()))

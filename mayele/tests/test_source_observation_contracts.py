from datetime import datetime, timedelta, timezone
from unittest import TestCase

from mayele.acquisition import DiscoveryResult
from mayele.common import KnowledgeScope, ScopeVisibility
from mayele.common.errors import MayeleContractError
from mayele.knowledge import Proposition, PropositionKind, Reality
from mayele.observation import (
    Mention,
    Observation,
    ObservationAttempt,
    ObservationAttemptOutcome,
    ObservationChannel,
    ObservedArtifact,
    ObservedStatement,
    Passage,
    Source,
    SourceKind,
    sha256_digest,
)


class SourceObservationContractTests(TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.source = Source(
            "source:university-x-admissions",
            SourceKind.WEB_PAGE,
            locator="https://example.test/admissions",
        )

    def successful_attempt(self, ref="attempt:1", when=None):
        return ObservationAttempt(
            ref,
            self.source,
            when or self.now,
            ObservationAttemptOutcome.SUCCESS,
            channel=ObservationChannel.WEB,
        )

    def observation(self, ref="observation:1", when=None):
        observed_at = when or self.now
        return Observation(
            ref,
            self.successful_attempt(f"attempt:{ref}", observed_at),
            observed_at,
        )

    def test_discovery_result_is_not_observation(self):
        result = DiscoveryResult(
            "discovery:1",
            "https://example.test/admissions",
            self.now,
            title="Admissions",
        )
        self.assertNotIsInstance(result, Observation)
        self.assertFalse(hasattr(result, "observed_at"))

    def test_failed_attempts_exist_without_successful_observation(self):
        for outcome in (
            ObservationAttemptOutcome.TIMEOUT,
            ObservationAttemptOutcome.DENIED,
            ObservationAttemptOutcome.NOT_FOUND,
            ObservationAttemptOutcome.FAILED,
        ):
            with self.subTest(outcome=outcome):
                attempt = ObservationAttempt(
                    f"attempt:{outcome.value.lower()}",
                    self.source,
                    self.now,
                    outcome,
                )
                self.assertEqual(attempt.outcome, outcome)
                with self.assertRaises(MayeleContractError):
                    Observation(
                        f"observation:{outcome.value.lower()}",
                        attempt,
                        self.now,
                    )

    def test_not_found_does_not_claim_world_nonexistence(self):
        attempt = ObservationAttempt(
            "attempt:not-found",
            self.source,
            self.now,
            ObservationAttemptOutcome.NOT_FOUND,
        )
        self.assertFalse(hasattr(attempt, "reality_ref"))
        self.assertFalse(hasattr(attempt, "proposition"))

    def test_observation_requires_timezone_aware_time(self):
        attempt = self.successful_attempt()
        with self.assertRaises(MayeleContractError):
            Observation(
                "observation:naive",
                attempt,
                datetime(2026, 10, 1, 8, 0, 0),
            )

    def test_same_content_digest_does_not_merge_observations(self):
        digest = sha256_digest("same received content")
        first = self.observation("observation:1", self.now)
        second_time = self.now + timedelta(hours=1)
        second = self.observation("observation:2", second_time)
        first_artifact = ObservedArtifact(
            "artifact:1",
            first,
            "text/html",
            content_digest=digest,
        )
        second_artifact = ObservedArtifact(
            "artifact:2",
            second,
            "text/html",
            content_digest=digest,
        )
        self.assertEqual(first_artifact.content_digest, second_artifact.content_digest)
        self.assertNotEqual(first.observation_ref, second.observation_ref)
        self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_passage_belongs_to_artifact(self):
        artifact = ObservedArtifact(
            "artifact:1",
            self.observation(),
            "application/pdf",
        )
        passage = Passage("passage:1", artifact, "page=17;paragraphs=2-4")
        self.assertIs(passage.artifact, artifact)

    def test_statement_lineage_reaches_source(self):
        observation = self.observation()
        artifact = ObservedArtifact("artifact:1", observation, "text/html")
        passage = Passage("passage:1", artifact, "section=deadlines")
        statement = ObservedStatement(
            "statement:1",
            passage,
            "Applications close on 31 January 2027.",
            language="en",
        )
        self.assertIs(
            statement.passage.artifact.observation.source,
            self.source,
        )

    def test_observed_statement_preserves_source_text_verbatim(self):
        artifact = ObservedArtifact(
            "artifact:1",
            self.observation(),
            "text/plain",
        )
        passage = Passage("passage:1", artifact, "lines=1-2")
        original = "Applications  close\n on 31 January 2027."
        statement = ObservedStatement("statement:1", passage, original)
        self.assertEqual(statement.text, original)

    def test_mention_is_not_reality_and_does_not_resolve_identity(self):
        artifact = ObservedArtifact(
            "artifact:1",
            self.observation(),
            "text/plain",
        )
        passage = Passage("passage:1", artifact, "line=1")
        statement = ObservedStatement(
            "statement:1",
            passage,
            "Applications must be submitted to University X.",
        )
        start = statement.text.index("University X")
        mention = Mention(
            "mention:1",
            statement,
            "University X",
            start=start,
            end=start + len("University X"),
        )
        self.assertNotIsInstance(mention, Reality)
        self.assertFalse(hasattr(mention, "reality_ref"))

    def test_statement_is_not_automatically_proposition(self):
        artifact = ObservedArtifact(
            "artifact:1",
            self.observation(),
            "text/plain",
        )
        passage = Passage("passage:1", artifact, "line=1")
        statement = ObservedStatement("statement:1", passage, "A source statement")
        proposition = Proposition(
            PropositionKind.REALITY_EXISTS,
            Reality("reality:x"),
        )
        self.assertNotIsInstance(statement, Proposition)
        self.assertFalse(hasattr(statement, "proposition"))
        self.assertNotEqual(type(statement), type(proposition))

    def test_private_scope_propagates_and_cannot_widen(self):
        private = KnowledgeScope(ScopeVisibility.PRIVATE, "profile:42")
        source = Source(
            "source:private",
            SourceKind.CONNECTED_FILE,
            scope=private,
            locator="drive:file:123",
        )
        attempt = ObservationAttempt(
            "attempt:private",
            source,
            self.now,
            ObservationAttemptOutcome.SUCCESS,
        )
        observation = Observation("observation:private", attempt, self.now)
        artifact = ObservedArtifact("artifact:private", observation, "text/plain")
        passage = Passage("passage:private", artifact, "line=1")
        statement = ObservedStatement("statement:private", passage, "Private text")
        self.assertEqual(statement.scope, private)

        with self.assertRaises(MayeleContractError):
            Observation(
                "observation:public",
                attempt,
                self.now,
                scope=KnowledgeScope(ScopeVisibility.PUBLIC),
            )

    def test_source_version_is_optional_not_invented(self):
        observation = self.observation()
        self.assertIsNone(observation.source_version_ref)

    def test_explicit_source_version_can_be_recorded(self):
        attempt = self.successful_attempt()
        observation = Observation(
            "observation:versioned",
            attempt,
            self.now,
            source_version_ref="etag:abc123",
        )
        self.assertEqual(observation.source_version_ref, "etag:abc123")

    def test_fingerprints_and_digests_are_deterministic(self):
        left = Source("source:x", SourceKind.API_ENDPOINT)
        right = Source("source:x", SourceKind.API_ENDPOINT)
        self.assertEqual(left.fingerprint, right.fingerprint)
        self.assertEqual(sha256_digest("abc"), sha256_digest(b"abc"))

    def test_public_artifact_metadata_rejects_secrets_and_credentials(self):
        observation = self.observation()
        for key in ("api_key", "access_token", "credential_ref"):
            with self.subTest(key=key):
                with self.assertRaises(MayeleContractError):
                    ObservedArtifact(
                        "artifact:unsafe",
                        observation,
                        "application/json",
                        metadata={key: "must-not-cross-public-contract"},
                    )

    def test_retry_link_is_technical_not_a_second_observation_by_itself(self):
        failed = ObservationAttempt(
            "attempt:first",
            self.source,
            self.now,
            ObservationAttemptOutcome.FAILED,
        )
        retry = ObservationAttempt(
            "attempt:retry",
            self.source,
            self.now + timedelta(seconds=5),
            ObservationAttemptOutcome.SUCCESS,
            retry_of_attempt_ref=failed.attempt_ref,
        )
        observation = Observation(
            "observation:after-retry",
            retry,
            self.now + timedelta(seconds=5),
        )
        self.assertEqual(retry.retry_of_attempt_ref, failed.attempt_ref)
        self.assertEqual(observation.attempt.attempt_ref, retry.attempt_ref)

from django.contrib.auth import get_user_model
from django.test import TestCase

from .knowledge import public_source_knowledge
from .models import OpportunityKind, OpportunitySourceCheckResult, OpportunitySourceType
from .services import (
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
    record_source_check,
    withdraw_opportunity,
)


class PublicSourceKnowledgeTests(TestCase):
    def setUp(self):
        self.curator = get_user_model().objects.create_user(
            username="knowledge-curator", email="knowledge@example.test",
            password="test-pass-2026", is_staff=True, is_superuser=True,
        )
        self.opportunity = create_opportunity(
            actor=self.curator, kind=OpportunityKind.SCHOLARSHIP,
        )
        self.revision = create_opportunity_revision(
            opportunity=self.opportunity, actor=self.curator,
            title="External scholarship", issuer_name="External organization",
            timezone_name="Africa/Lubumbashi",
        )
        self.source = create_opportunity_source(
            opportunity=self.opportunity, actor=self.curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Official",
            url="https://example.test/source",
            is_primary=True, verified=True,
        )

    def publish(self):
        publish_opportunity_revision(
            opportunity=self.opportunity, revision=self.revision,
            actor=self.curator,
        )

    def test_draft_has_no_public_knowledge(self):
        self.assertIsNone(public_source_knowledge(self.opportunity.pk))

    def test_published_source_verification_does_not_assert_fact_freshness(self):
        self.publish()
        knowledge = public_source_knowledge(self.opportunity.pk)
        self.assertEqual(knowledge["fact_freshness"], "not_asserted")
        self.assertEqual(knowledge["revision"]["id"], str(self.revision.pk))
        self.assertIsNotNone(knowledge["revision_published_at"])
        self.assertEqual(len(knowledge["source_observations"]), 1)
        source = knowledge["source_observations"][0]
        self.assertTrue(source["primary"])
        self.assertIsNotNone(source["verified_at"])
        self.assertIsNone(source["last_checked_at"])
        self.assertNotIn("url", source)
        self.assertNotIn("verified_by", source)

    def test_check_observation_is_explicit_but_not_a_fact_certificate(self):
        self.publish()
        check = record_source_check(
            source=self.source, result=OpportunitySourceCheckResult.UNCHANGED,
            checked_by=self.curator, fingerprint="internal-fingerprint",
            note="private operational note",
        )
        knowledge = public_source_knowledge(self.opportunity.pk)
        observation = knowledge["source_observations"][0]
        self.assertEqual(observation["last_checked_at"], check.checked_at.isoformat())
        self.assertNotIn("fingerprint", str(knowledge))
        self.assertNotIn("private operational note", str(knowledge))
        self.assertEqual(knowledge["fact_freshness"], "not_asserted")

    def test_withdrawn_opportunity_is_not_public(self):
        self.publish()
        withdraw_opportunity(opportunity=self.opportunity, actor=self.curator)
        self.assertIsNone(public_source_knowledge(self.opportunity.pk))

    def test_removed_source_is_not_exposed_as_active_evidence(self):
        self.publish()
        record_source_check(
            source=self.source, result=OpportunitySourceCheckResult.REMOVED,
            checked_by=self.curator,
        )
        knowledge = public_source_knowledge(self.opportunity.pk)
        self.assertEqual(knowledge["source_observations"], [])
        self.assertEqual(knowledge["fact_freshness"], "not_asserted")

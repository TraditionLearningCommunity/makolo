from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from domain_events.models import DomainEventOutbox
from geography.models import Zone

from .models import (
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRequirementKind,
    OpportunitySave,
    OpportunitySourceCheckResult,
    OpportunitySourceStatus,
    OpportunitySourceType,
    OpportunitySubmissionStatus,
    OpportunityZoneRole,
)
from .selectors import closed_opportunities, open_opportunities, opportunities_for_zone, published_opportunities, upcoming_opportunities
from .services import (
    add_opportunity_zone,
    add_requirement,
    archive_opportunity,
    canonical_opportunity,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    decide_opportunity_submission,
    merge_opportunities,
    publish_opportunity_revision,
    record_source_check,
    save_opportunity,
    start_submission_review,
    submit_opportunity,
    unsave_opportunity,
    withdraw_opportunity,
)


User = get_user_model()


class OpportunityDomainTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="opp-staff", email="opp-staff@example.com", password="x", is_superuser=True, is_staff=True)
        self.participant = User.objects.create_user(username="opp-user", email="opp-user@example.com", password="x")
        self.other = User.objects.create_user(username="opp-other", email="opp-other@example.com", password="x")
        self.zone = Zone.objects.create(name="Kinshasa", country_code="CD", administrative_area="Kinshasa", created_by=self.staff)

    def _draft(self, kind=OpportunityKind.JOB):
        opportunity = create_opportunity(actor=self.staff, kind=kind)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.staff, title="Développeur backend", issuer_name="Entreprise externe", summary="Poste externe", timezone_name="Africa/Lubumbashi")
        return opportunity, revision

    def _publishable(self, kind=OpportunityKind.JOB, **revision_overrides):
        opportunity = create_opportunity(actor=self.staff, kind=kind)
        params = {"title": "Développeur backend", "issuer_name": "Entreprise externe", "summary": "Poste externe", "timezone_name": "Africa/Lubumbashi"}
        params.update(revision_overrides)
        revision = create_opportunity_revision(opportunity=opportunity, actor=self.staff, **params)
        create_opportunity_source(opportunity=opportunity, actor=self.staff, source_type=OpportunitySourceType.OFFICIAL, source_name="Site officiel", url="https://example.test/opportunity", is_primary=True, verified=True)
        return opportunity, revision

    def test_non_curator_cannot_create(self):
        with self.assertRaises(PermissionDenied):
            create_opportunity(actor=self.participant, kind=OpportunityKind.JOB)

    def test_publish_requires_primary_source_and_pins_revision(self):
        opportunity, revision = self._draft()
        with self.assertRaises(ValidationError):
            publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.staff)
        create_opportunity_source(opportunity=opportunity, actor=self.staff, source_type=OpportunitySourceType.OFFICIAL, source_name="Official", url="https://example.test/official", is_primary=True)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.staff)
        opportunity.refresh_from_db(); revision.refresh_from_db()
        self.assertEqual(opportunity.publication_status, OpportunityPublicationStatus.PUBLISHED)
        self.assertEqual(opportunity.current_revision_id, revision.pk)
        self.assertIsNotNone(opportunity.published_at)
        self.assertIsNotNone(revision.published_at)
        self.assertTrue(DomainEventOutbox.objects.filter(event_type="opportunity.revision.published", source_id=str(revision.pk)).exists())

    def test_published_revision_remains_immutable_after_v2(self):
        opportunity, revision1 = self._publishable()
        publish_opportunity_revision(opportunity=opportunity, revision=revision1, actor=self.staff)
        revision2 = create_opportunity_revision(opportunity=opportunity, actor=self.staff, title="Développeur backend senior", issuer_name="Entreprise externe", timezone_name="Africa/Lubumbashi", change_summary="Mise à jour")
        publish_opportunity_revision(opportunity=opportunity, revision=revision2, actor=self.staff)
        revision1.title = "Mutation interdite"
        with self.assertRaises(ValidationError):
            revision1.save()
        with self.assertRaises(ValidationError):
            revision1.delete()
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.current_revision_id, revision2.pk)

    def test_temporal_states_and_public_selectors(self):
        now = timezone.now()
        upcoming, upcoming_rev = self._publishable(opens_at=now + timedelta(days=1), deadline_at=now + timedelta(days=4))
        publish_opportunity_revision(opportunity=upcoming, revision=upcoming_rev, actor=self.staff)
        opened, opened_rev = self._publishable(opens_at=now - timedelta(days=1), deadline_at=now + timedelta(days=2))
        publish_opportunity_revision(opportunity=opened, revision=opened_rev, actor=self.staff)
        closed, closed_rev = self._publishable(opens_at=now - timedelta(days=4), deadline_at=now)
        publish_opportunity_revision(opportunity=closed, revision=closed_rev, actor=self.staff)
        draft, _ = self._draft()
        self.assertEqual(upcoming_rev.temporal_state(at=now), "upcoming")
        self.assertEqual(opened_rev.temporal_state(at=now), "open")
        self.assertEqual(closed_rev.temporal_state(at=now), "closed")
        self.assertIn(upcoming, upcoming_opportunities(at=now))
        self.assertIn(opened, open_opportunities(at=now))
        self.assertIn(closed, closed_opportunities(at=now))
        self.assertNotIn(draft, published_opportunities())

    def test_invalid_timezone_and_deadline_are_rejected(self):
        opportunity = create_opportunity(actor=self.staff, kind=OpportunityKind.JOB)
        with self.assertRaises(ValidationError):
            create_opportunity_revision(opportunity=opportunity, actor=self.staff, title="X", issuer_name="Y", timezone_name="Not/AZone")
        now = timezone.now()
        with self.assertRaises(ValidationError):
            create_opportunity_revision(opportunity=opportunity, actor=self.staff, title="X", issuer_name="Y", timezone_name="Africa/Lubumbashi", opens_at=now, deadline_at=now)

    def test_zones_requirements_and_published_immutability(self):
        opportunity, revision = self._publishable(kind=OpportunityKind.SCHOLARSHIP)
        relation = add_opportunity_zone(revision=revision, zone=self.zone, role=OpportunityZoneRole.ELIGIBILITY, actor=self.staff)
        requirement = add_requirement(revision=revision, actor=self.staff, kind=OpportunityRequirementKind.EDUCATION, title="Diplôme", position=10)
        self.assertEqual(relation.zone_id, self.zone.pk)
        self.assertEqual(requirement.revision_id, revision.pk)
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.staff)
        self.assertIn(opportunity, opportunities_for_zone(self.zone, role=OpportunityZoneRole.ELIGIBILITY))
        with self.assertRaises(ValidationError):
            add_requirement(revision=revision, actor=self.staff, kind=OpportunityRequirementKind.DOCUMENT, title="CV")
        with self.assertRaises(ValidationError):
            relation.delete()

    def test_primary_source_and_source_checks_append_only(self):
        opportunity, _ = self._draft()
        source = create_opportunity_source(opportunity=opportunity, actor=self.staff, source_type=OpportunitySourceType.OFFICIAL, source_name="Official", url="https://example.test/a", is_primary=True)
        with self.assertRaises(ValidationError):
            create_opportunity_source(opportunity=opportunity, actor=self.staff, source_type=OpportunitySourceType.TRUSTED_PARTNER, source_name="Partner", url="https://example.test/b", is_primary=True)
        check = record_source_check(source=source, result=OpportunitySourceCheckResult.CHANGED, checked_by=self.staff, fingerprint="abc")
        source.refresh_from_db()
        self.assertEqual(source.status, OpportunitySourceStatus.CHANGED)
        self.assertTrue(DomainEventOutbox.objects.filter(event_type="opportunity.source.changed", source_id=str(check.pk)).exists())
        check.note = "rewrite"
        with self.assertRaises(ValidationError):
            check.save()
        with self.assertRaises(ValidationError):
            check.delete()

    def test_save_unsave_and_merge_consolidate_to_canonical(self):
        canonical, _ = self._draft()
        duplicate, _ = self._draft()
        first = save_opportunity(profile=self.participant, opportunity=duplicate)
        second = save_opportunity(profile=self.participant, opportunity=duplicate)
        self.assertEqual(first.pk, second.pk)
        merge_opportunities(canonical=canonical, duplicate=duplicate, actor=self.staff)
        duplicate.refresh_from_db()
        self.assertEqual(canonical_opportunity(duplicate).pk, canonical.pk)
        self.assertEqual(OpportunitySave.objects.filter(profile=self.participant, opportunity=canonical).count(), 1)
        self.assertFalse(OpportunitySave.objects.filter(profile=self.participant, opportunity=duplicate).exists())
        redirected = save_opportunity(profile=self.participant, opportunity=duplicate)
        self.assertEqual(redirected.opportunity_id, canonical.pk)
        self.assertTrue(unsave_opportunity(profile=self.participant, opportunity=duplicate))

    def test_submission_transitions_and_non_curator_denied(self):
        opportunity, _ = self._draft()
        submission = submit_opportunity(submitted_by=self.participant, url="https://example.test/user", title="Suggestion")
        with self.assertRaises(PermissionDenied):
            start_submission_review(submission=submission, actor=self.other)
        start_submission_review(submission=submission, actor=self.staff)
        decided = decide_opportunity_submission(submission=submission, actor=self.staff, decision=OpportunitySubmissionStatus.ACCEPTED, resolved_opportunity=opportunity)
        self.assertEqual(decided.status, OpportunitySubmissionStatus.ACCEPTED)
        self.assertEqual(decided.resolved_opportunity_id, opportunity.pk)
        with self.assertRaises(ValidationError):
            decide_opportunity_submission(submission=decided, actor=self.staff, decision=OpportunitySubmissionStatus.REJECTED)

    def test_withdraw_and_archive_keep_history(self):
        opportunity, revision = self._publishable()
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.staff)
        withdraw_opportunity(opportunity=opportunity, actor=self.staff)
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.publication_status, OpportunityPublicationStatus.WITHDRAWN)
        self.assertTrue(DomainEventOutbox.objects.filter(event_type="opportunity.withdrawn", source_id=str(opportunity.pk)).exists())
        archive_opportunity(opportunity=opportunity, actor=self.staff)
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.publication_status, OpportunityPublicationStatus.ARCHIVED)
        self.assertTrue(opportunity.revisions.filter(pk=revision.pk).exists())

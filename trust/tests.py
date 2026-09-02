import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import ensure_platform_admin_mandate, grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus

from .models import (
    Feedback,
    FeedbackAnswer,
    FeedbackSentiment,
    ProofStatus,
    ProofType,
    ReportCategory,
    ReportStatus,
    VerificationClaim,
    VerificationClaimType,
    VerificationDisclosure,
    VerificationStatus,
)
from .selectors import get_public_trust_summary, public_proof_by_id
from .services import (
    attach_trust_evidence,
    can_access_evidence,
    can_submit_feedback,
    close_dispute,
    create_report,
    decide_dispute,
    decide_verification,
    issue_proof,
    open_dispute,
    request_dispute_information,
    request_verification,
    resolve_report,
    revoke_proof,
    revoke_verification,
    start_verification_review,
    submit_feedback,
    triage_report,
)


User = get_user_model()


class TrustFixtureMixin:
    def build_fixture(self):
        self.owner = User.objects.create_user(username="trust-owner", email="owner@trust.test", password="StrongPass2026!")
        self.participant = User.objects.create_user(username="trust-participant", email="participant@trust.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="trust-outsider", email="outsider@trust.test", password="StrongPass2026!")
        self.staff = User.objects.create_user(username="trust-staff", email="staff@trust.test", password="StrongPass2026!", is_staff=True)
        self.space = Organization.objects.create(name="Trust Space", created_by=self.owner, public_profile=True)
        grant_space_role(profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER, source="m4-test")
        ensure_platform_admin_mandate(profile=self.staff, source="m4-test")
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Trust Activity", status=ActivityStatus.PUBLISHED)
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(activity=self.activity, label="Session", start_at=now-timedelta(hours=2), end_at=now-timedelta(hours=1), status=OccurrenceStatus.COMPLETED)
        self.fulfilled = Journey.objects.create(initiated_by=self.participant, beneficiary=self.participant, activity=self.activity, occurrence=self.occurrence, workflow=WorkflowKind.REGISTRATION, status=JourneyStatus.FULFILLED, fulfilled_at=now-timedelta(minutes=50))
        self.future_occurrence = Occurrence.objects.create(activity=self.activity, label="Future", start_at=now+timedelta(days=2), end_at=now+timedelta(days=2, hours=1), status=OccurrenceStatus.SCHEDULED)
        self.future_journey = Journey.objects.create(initiated_by=self.participant, beneficiary=self.participant, activity=self.activity, occurrence=self.future_occurrence, workflow=WorkflowKind.REGISTRATION, status=JourneyStatus.CONFIRMED)


class VerificationWorkflowTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_space_owner_with_mandate_can_request_but_member_without_mandate_cannot(self):
        claim = request_verification(actor=self.owner, subject_space=self.space, claim_type=VerificationClaimType.ORGANIZATION_IDENTITY)
        self.assertEqual(claim.status, VerificationStatus.REQUESTED)
        member = User.objects.create_user(username="member-only", email="member@trust.test", password="StrongPass2026!")
        team = Team.objects.create(organization=self.space, name="Trust team", is_default=True)
        TeamMembership.objects.create(team=team, user=member, status=TeamMembershipStatus.ACTIVE, joined_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            request_verification(actor=member, subject_space=self.space, claim_type=VerificationClaimType.ORGANIZATION_IDENTITY)

    def test_platform_review_verify_reject_and_self_verification_guard(self):
        claim = request_verification(actor=self.owner, subject_space=self.space, claim_type=VerificationClaimType.ORGANIZATION_IDENTITY)
        reviewed = start_verification_review(claim=claim, actor=self.staff)
        self.assertEqual(reviewed.status, VerificationStatus.UNDER_REVIEW)
        verified = decide_verification(claim=reviewed, actor=self.staff, verified=True, reason_code="documents_match")
        self.assertTrue(verified.is_currently_verified)
        profile_claim = request_verification(actor=self.staff, subject_profile=self.staff, claim_type=VerificationClaimType.PROFILE_IDENTITY)
        with self.assertRaises(PermissionDenied):
            start_verification_review(claim=profile_claim, actor=self.staff)
        second = request_verification(actor=self.participant, subject_profile=self.participant, claim_type=VerificationClaimType.PROFILE_IDENTITY)
        rejected = decide_verification(claim=second, actor=self.staff, verified=False, reason_code="insufficient_evidence")
        self.assertEqual(rejected.status, VerificationStatus.REJECTED)

    def test_expired_and_revoked_claims_are_not_publicly_active(self):
        now = timezone.now()
        expired = VerificationClaim.objects.create(subject_space=self.space, claim_type=VerificationClaimType.ORGANIZATION_IDENTITY, status=VerificationStatus.VERIFIED, disclosure=VerificationDisclosure.PUBLIC_RESULT, requested_by=self.owner, reviewed_by=self.staff, reviewed_at=now-timedelta(days=10), valid_from=now-timedelta(days=10), valid_until=now-timedelta(days=1))
        self.assertFalse(expired.is_currently_verified)
        self.assertEqual(get_public_trust_summary(self.space)["verification"], [])
        claim = request_verification(actor=self.owner, subject_space=self.space, claim_type=VerificationClaimType.CONTACT)
        claim = decide_verification(claim=claim, actor=self.staff, verified=True)
        revoke_verification(claim=claim, actor=self.staff, reason_code="withdrawn")
        self.assertEqual(get_public_trust_summary(self.space)["verification"], [])

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_evidence_is_private_and_not_exposed_by_public_projection(self):
        claim = request_verification(actor=self.owner, subject_space=self.space, claim_type=VerificationClaimType.ORGANIZATION_IDENTITY)
        upload = SimpleUploadedFile("proof.pdf", b"%PDF-1.4\nminimal", content_type="application/pdf")
        evidence = attach_trust_evidence(actor=self.owner, uploaded_file=upload, verification_claim=claim)
        self.assertTrue(can_access_evidence(evidence=evidence, actor=self.owner))
        self.assertTrue(can_access_evidence(evidence=evidence, actor=self.staff))
        self.assertFalse(can_access_evidence(evidence=evidence, actor=self.outsider))
        summary = get_public_trust_summary(self.space)
        self.assertNotIn("evidence", summary)
        self.assertNotIn("decision_note_private", str(summary))


class FeedbackWorkflowTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_real_participant_can_submit_once_and_stranger_or_too_early_cannot(self):
        self.assertTrue(can_submit_feedback(journey=self.fulfilled, actor=self.participant))
        feedback = submit_feedback(journey=self.fulfilled, actor=self.participant, delivery=FeedbackAnswer.YES, overall_sentiment=FeedbackSentiment.NEGATIVE, comment="Expérience réelle")
        self.assertEqual(feedback.overall_sentiment, FeedbackSentiment.NEGATIVE)
        with self.assertRaises(PermissionDenied):
            submit_feedback(journey=self.fulfilled, actor=self.participant)
        with self.assertRaises(PermissionDenied):
            submit_feedback(journey=self.future_journey, actor=self.participant)
        with self.assertRaises(PermissionDenied):
            submit_feedback(journey=self.future_journey, actor=self.outsider)

    def test_access_dimension_is_not_accepted_when_not_applicable(self):
        with self.assertRaises(ValidationError):
            submit_feedback(journey=self.fulfilled, actor=self.participant, access_experience=FeedbackAnswer.YES)

    def test_negative_feedback_does_not_change_canonical_journey_or_occurrence(self):
        submit_feedback(journey=self.fulfilled, actor=self.participant, overall_sentiment=FeedbackSentiment.NEGATIVE)
        self.fulfilled.refresh_from_db(); self.occurrence.refresh_from_db()
        self.assertEqual(self.fulfilled.status, JourneyStatus.FULFILLED)
        self.assertEqual(self.occurrence.status, OccurrenceStatus.COMPLETED)

    def test_small_samples_do_not_publish_sentiment_breakdown(self):
        submit_feedback(journey=self.fulfilled, actor=self.participant, overall_sentiment=FeedbackSentiment.POSITIVE)
        summary = get_public_trust_summary(self.space)
        self.assertEqual(summary["feedback"]["verified_experiences"], 1)
        self.assertFalse(summary["feedback"]["breakdown_available"])
        self.assertNotIn("sentiment", summary["feedback"])
        self.assertNotIn("score", str(summary).lower())


class ReportsAndDisputesTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_report_context_idor_and_staff_lifecycle(self):
        report = create_report(actor=self.participant, journey=self.fulfilled, category=ReportCategory.SERVICE_NOT_DELIVERED, description="Le service annoncé n’a pas été délivré")
        self.assertEqual(report.activity_id, self.activity.pk)
        with self.assertRaises(PermissionDenied):
            create_report(actor=self.outsider, journey=self.fulfilled, category=ReportCategory.OTHER, description="foreign")
        with self.assertRaises(PermissionDenied):
            resolve_report(report=report, actor=self.owner, resolution_code="owner_cannot_resolve")
        triage_report(report=report, actor=self.staff, investigate=True)
        report.refresh_from_db(); self.assertEqual(report.status, ReportStatus.INVESTIGATING)
        resolved = resolve_report(report=report, actor=self.staff, resolution_code="confirmed_issue")
        self.assertEqual(resolved.status, ReportStatus.RESOLVED)

    def test_dispute_decision_and_close_are_explicit_and_idempotent(self):
        report = create_report(actor=self.participant, journey=self.fulfilled, category=ReportCategory.OTHER, description="Dossier formel")
        dispute = open_dispute(report=report, actor=self.staff)
        self.assertEqual(open_dispute(report=report, actor=self.staff).pk, dispute.pk)
        request_dispute_information(dispute=dispute, actor=self.staff)
        dispute = decide_dispute(dispute=dispute, actor=self.staff, decision_code="operator_correction", decision_summary="Une correction opérateur est requise.", remedy_code="correction_required")
        self.assertEqual(dispute.status, "decided")
        dispute = close_dispute(dispute=dispute, actor=self.staff)
        closed_at = dispute.closed_at
        dispute = close_dispute(dispute=dispute, actor=self.staff)
        self.assertEqual(dispute.closed_at, closed_at)

    def test_unresolved_report_is_not_in_public_trust_summary(self):
        create_report(actor=self.participant, journey=self.fulfilled, category=ReportCategory.OTHER, description="Non résolu")
        summary = get_public_trust_summary(self.space)
        self.assertNotIn("issues", summary)
        self.assertNotIn("report", str(summary).lower())

    def test_report_text_is_escaped_in_web_surface_and_private_note_not_rendered(self):
        report = create_report(actor=self.participant, journey=self.fulfilled, category=ReportCategory.OTHER, description="<script>alert('x')</script>")
        report.staff_note_private = "SECRET-STAFF-NOTE"; report.save(update_fields=["staff_note_private", "updated_at"])
        self.client.force_login(self.participant)
        response = self.client.get(reverse("trust:report-detail", kwargs={"report_id": report.pk}))
        self.assertContains(response, "&lt;script&gt;", html=False)
        self.assertNotContains(response, "SECRET-STAFF-NOTE")


class ReputationProjectionTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_reliability_keeps_denominators_period_sources_and_no_universal_score(self):
        summary = get_public_trust_summary(self.space)
        metrics = {item["key"]: item for item in summary["operations"]["metrics"]}
        self.assertEqual(metrics["occurrence_completion"]["numerator"], 1)
        self.assertEqual(metrics["occurrence_completion"]["denominator"], 1)
        self.assertEqual(metrics["journey_fulfillment"]["numerator"], 1)
        self.assertEqual(metrics["journey_fulfillment"]["denominator"], 1)
        for metric in metrics.values():
            self.assertEqual(metric["period_days"], 365)
            self.assertTrue(metric["source"])
        self.assertNotIn("reputation_score", str(summary))
        self.assertNotIn("followers", str(summary))

    def test_public_projection_is_query_bounded(self):
        with self.assertNumQueries(4):
            get_public_trust_summary(self.space)


class ProofTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_valid_fact_issues_idempotent_proof_for_beneficiary(self):
        proof = issue_proof(journey=self.fulfilled, proof_type=ProofType.JOURNEY_COMPLETED, actor=self.staff, is_public=True)
        second = issue_proof(journey=self.fulfilled, proof_type=ProofType.JOURNEY_COMPLETED, actor=self.staff, is_public=True)
        self.assertEqual(second.pk, proof.pk)
        self.assertEqual(proof.subject_profile_id, self.participant.pk)
        self.assertIsNotNone(public_proof_by_id(proof.public_id))

    def test_missing_fact_refuses_proof(self):
        with self.assertRaises(ValidationError):
            issue_proof(journey=self.future_journey, proof_type=ProofType.JOURNEY_COMPLETED, actor=self.staff)

    def test_public_lookup_requires_explicit_visibility_and_revocation_remains_verifiable(self):
        proof = issue_proof(journey=self.fulfilled, proof_type=ProofType.JOURNEY_COMPLETED, actor=self.staff, is_public=False)
        self.assertIsNone(public_proof_by_id(proof.public_id))
        proof.is_public = True; proof.save(update_fields=["is_public", "updated_at"])
        proof = revoke_proof(proof=proof, actor=self.staff, reason="source corrected")
        visible = public_proof_by_id(proof.public_id)
        self.assertEqual(visible.status, ProofStatus.REVOKED)
        self.client.logout()
        response = self.client.get(reverse("trust:proof-verify", kwargs={"public_id": proof.public_id}))
        self.assertContains(response, "révoquée", status_code=200)

    def test_proof_list_is_owner_scoped(self):
        issue_proof(journey=self.fulfilled, proof_type=ProofType.JOURNEY_COMPLETED, actor=self.staff)
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("trust:my-proofs"))
        self.assertNotContains(response, self.activity.title)

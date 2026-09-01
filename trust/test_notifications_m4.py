from django.test import TestCase

from notifications.models import Notification

from .models import ProofType, ReportCategory, VerificationClaimType
from .services import (
    create_report,
    decide_dispute,
    decide_verification,
    issue_proof,
    open_dispute,
    request_verification,
    revoke_proof,
)
from .tests import TrustFixtureMixin


class TrustLifecycleNotificationTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_verification_decision_notification_contains_no_private_note(self):
        claim = request_verification(
            actor=self.owner,
            subject_space=self.space,
            claim_type=VerificationClaimType.ORGANIZATION_IDENTITY,
        )
        decide_verification(
            claim=claim,
            actor=self.staff,
            verified=True,
            reason_code="documents_match",
            private_note="PRIVATE REVIEW NOTE",
        )
        texts = " ".join(Notification.objects.filter(recipient=self.owner).values_list("message", flat=True))
        self.assertIn("claim de vérification", texts)
        self.assertNotIn("PRIVATE REVIEW NOTE", texts)

    def test_report_dispute_and_proof_notifications_are_deduplicated_and_minimal(self):
        report = create_report(
            actor=self.participant,
            journey=self.fulfilled,
            category=ReportCategory.OTHER,
            description="PRIVATE REPORT BODY",
        )
        self.assertEqual(
            Notification.objects.filter(dedup_key=f"trust:report:{report.pk}:created").count(),
            1,
        )
        dispute = open_dispute(report=report, actor=self.staff)
        decide_dispute(
            dispute=dispute,
            actor=self.staff,
            decision_code="resolved",
            decision_summary="Public result",
            private_note="PRIVATE DISPUTE NOTE",
        )
        proof = issue_proof(
            journey=self.fulfilled,
            proof_type=ProofType.JOURNEY_COMPLETED,
            actor=self.staff,
        )
        revoke_proof(proof=proof, actor=self.staff, reason="source corrected")

        payload = " ".join(
            Notification.objects.filter(recipient=self.participant).values_list("title", "message")
        )
        self.assertNotIn("PRIVATE REPORT BODY", payload)
        self.assertNotIn("PRIVATE DISPUTE NOTE", payload)
        self.assertGreaterEqual(Notification.objects.filter(recipient=self.participant).count(), 5)

from datetime import timedelta

from django.utils import timezone

from personal_assets.action_memory import ActionMemorySource
from requirements.contracts import RequirementAssessmentState
from requirements.models import RequirementReuseApplication

from .test_q4_trusted_reuse import TrustedReuseQ4Tests
from .trusted_reuse import apply_trusted_reuse, evaluate_trusted_reuse


class TrustedReuseAuditQ4Tests(TrustedReuseQ4Tests.__bases__[0]):
    setUp = TrustedReuseQ4Tests.setUp
    _assessment = TrustedReuseQ4Tests._assessment
    _asset_version = TrustedReuseQ4Tests._asset_version
    _candidate = TrustedReuseQ4Tests._candidate
    _active_proof = TrustedReuseQ4Tests._active_proof

    def test_document_application_audit_is_exact_private_and_idempotent(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)

        first = apply_trusted_reuse(
            assessment=assessment,
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.LIBRARY,
            candidate_source_id=version.pk,
        )
        second = apply_trusted_reuse(
            assessment=assessment,
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.LIBRARY,
            candidate_source_id=version.pk,
        )

        self.assertEqual(first.application_id, second.application_id)
        audit = RequirementReuseApplication.objects.get(pk=first.application_id)
        self.assertEqual(audit.source_asset_version_id, version.pk)
        self.assertEqual(audit.policy.requirement_id, assessment.requirement_id)
        self.assertEqual(audit.materialized_artifact_id, first.journey_artifact_id)
        self.assertEqual(audit.evidence_id, first.evidence_id)
        self.assertEqual(audit.applied_by_id, self.beneficiary.pk)
        self.assertEqual(RequirementReuseApplication.objects.filter(assessment=assessment).count(), 1)
        self.assertFalse(hasattr(audit, "content_hash"))
        self.assertFalse(hasattr(audit, "filename"))

    def test_active_proof_apply_creates_audit_only_and_never_fake_artifact(self):
        proof = self._active_proof()
        assessment = self._assessment(self.proof_requirement)
        before_artifacts = self.journey.artifacts.count()

        result = apply_trusted_reuse(
            assessment=assessment,
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.PROOF,
            candidate_source_id=proof.pk,
        )

        self.assertIsNone(result.journey_artifact_id)
        self.assertIsNone(result.evidence_id)
        audit = RequirementReuseApplication.objects.get(pk=result.application_id)
        self.assertEqual(audit.source_proof_id, proof.pk)
        self.assertIsNone(audit.materialized_artifact_id)
        self.assertIsNone(audit.evidence_id)
        self.assertEqual(self.journey.artifacts.count(), before_artifacts)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, RequirementAssessmentState.UNASSESSED)

    def test_max_age_requires_explicit_source_date_not_creation_fallback(self):
        _, version = self._asset_version(text=b"no-issued-date")
        candidate = self._candidate(version.pk)
        self.assertIsNotNone(candidate.relevant_at)

        decision = evaluate_trusted_reuse(
            assessment=self._assessment(self.window_requirement),
            candidate=candidate,
            actor=self.beneficiary,
        )

        self.assertEqual(decision.decision.value, "unknown")
        self.assertIn("reuse.freshness_unknown", {reason.value for reason in decision.reasons})

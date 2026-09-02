from dataclasses import replace
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact
from journeys.models import ExternalBeneficiary, JourneyStatus, WorkflowKind
from journeys.services import create_journey
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import add_requirement, create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision
from personal_assets.action_memory import ActionMemorySource, ActionMemorySubject, ActionMemorySubjectType, action_memory_for_journey
from personal_assets.models import PersonalAssetUse, PersonalAssetVersion
from personal_assets.services import archive_personal_asset, create_personal_asset, create_personal_asset_version
from requirements.contracts import RequirementAssessmentState
from requirements.models import RequirementReusePolicy, RequirementReuseSource
from requirements.trusted_reuse import TrustedReuseDecisionCode, TrustedReuseReasonCode
from trust.models import Proof, ProofType
from trust.services import revoke_proof

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementEvidence
from .requirement_services import assess_requirement
from .services import create_service_details, create_service_journey
from .trusted_reuse import apply_trusted_reuse, evaluate_trusted_reuse

User = get_user_model()


def pdf_upload(text=b"q4"):
    return SimpleUploadedFile("document.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class TrustedReuseQ4Tests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="q4-curator", email="q4-curator@example.test", password="x", is_staff=True, is_superuser=True)
        self.manager = User.objects.create_user(username="q4-manager", email="q4-manager@example.test", password="x")
        self.beneficiary = User.objects.create_user(username="q4-beneficiary", email="q4-beneficiary@example.test", password="x")
        self.other = User.objects.create_user(username="q4-other", email="q4-other@example.test", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Q4 Trusted Reuse")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT, opportunity_policy=OpportunityPolicy.REQUIRED, allows_external_beneficiary=True)
        self.opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.SCHOLARSHIP)
        self.revision = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Q4 opportunity", issuer_name="Q4 issuer", timezone_name="UTC")
        create_opportunity_source(opportunity=self.opportunity, actor=self.curator, source_type=OpportunitySourceType.OFFICIAL, source_name="Q4 official", url=f"https://example.test/q4/{self.opportunity.pk}", is_primary=True, verified=True)
        self.doc_requirement = self._add_requirement("Document structuré", OpportunityRequirementKind.DOCUMENT, 10)
        self.window_requirement = self._add_requirement("Document récent", OpportunityRequirementKind.DOCUMENT, 20)
        self.history_requirement = self._add_requirement("Certificat historique", OpportunityRequirementKind.DOCUMENT, 30)
        self.proof_requirement = self._add_requirement("Service accompli", OpportunityRequirementKind.ELIGIBILITY, 40)
        self.no_policy_requirement = self._add_requirement("Sans policy", OpportunityRequirementKind.DOCUMENT, 50)
        RequirementReusePolicy.objects.create(requirement=self.doc_requirement, key="library-cv", source_type=RequirementReuseSource.LIBRARY, artifact_kind=JourneyArtifactKind.CV, require_not_expired=True, allow_sensitive_with_confirmation=True, allow_restricted_with_confirmation=True)
        RequirementReusePolicy.objects.create(requirement=self.window_requirement, key="recent-cv", source_type=RequirementReuseSource.LIBRARY, artifact_kind=JourneyArtifactKind.CV, require_not_expired=False, max_age_days=90)
        RequirementReusePolicy.objects.create(requirement=self.history_requirement, key="historical-certificate", source_type=RequirementReuseSource.JOURNEY_ARTIFACT, artifact_kind=JourneyArtifactKind.CERTIFICATE, require_not_expired=False)
        RequirementReusePolicy.objects.create(requirement=self.proof_requirement, key="service-completed", source_type=RequirementReuseSource.PROOF, proof_type=ProofType.SERVICE_COMPLETED)
        publish_opportunity_revision(opportunity=self.opportunity, revision=self.revision, actor=self.curator)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, opportunity=self.opportunity)
        self.assessments = {item.requirement_id: item for item in self.journey.service_context.requirement_assessments.select_related("requirement")}

    def _add_requirement(self, title, kind, position):
        return add_requirement(revision=self.revision, actor=self.curator, kind=kind, title=title, position=position)

    def _assessment(self, requirement):
        return self.assessments[requirement.pk]

    def _asset_version(self, *, controller=None, subject=None, external_subject=None, kind=JourneyArtifactKind.CV, sensitivity=JourneyArtifactSensitivity.NORMAL, issued_at=None, expires_at=None, text=b"library-v1"):
        controller = controller or self.beneficiary
        kwargs = {"controller": controller, "title": "Document Q4", "kind": kind, "sensitivity": sensitivity}
        if external_subject is not None:
            kwargs["subject_external_beneficiary"] = external_subject
        else:
            kwargs["subject_profile"] = subject or self.beneficiary
        asset = create_personal_asset(**kwargs)
        version = create_personal_asset_version(actor=controller, asset=asset, uploaded_file=pdf_upload(text), issued_at=issued_at, expires_at=expires_at)
        return asset, version

    def _candidate(self, source_id, *, actor=None, journey=None, observed_at=None):
        candidates = action_memory_for_journey(actor=actor or self.beneficiary, journey=journey or self.journey, observed_at=observed_at)
        return next(item for item in candidates if item.source_id == str(source_id))

    def _active_proof(self):
        old = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.FULFILLED)
        return Proof.objects.create(subject_profile=self.beneficiary, journey=old, proof_type=ProofType.SERVICE_COMPLETED)

    def test_no_policy_returns_unknown_without_mutation(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.no_policy_requirement)
        before = (assessment.status, ServiceRequirementEvidence.objects.count(), self.journey.artifacts.count())
        decision = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(version.pk), actor=self.beneficiary)
        self.assertEqual(decision.decision, TrustedReuseDecisionCode.UNKNOWN)
        self.assertIn(TrustedReuseReasonCode.NO_POLICY, decision.reasons)
        assessment.refresh_from_db()
        self.assertEqual(before, (assessment.status, ServiceRequirementEvidence.objects.count(), self.journey.artifacts.count()))

    def test_exact_kind_and_wrong_kind_are_rule_based(self):
        _, cv = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        _, certificate = self._asset_version(kind=JourneyArtifactKind.CERTIFICATE, expires_at=timezone.localdate() + timedelta(days=30), text=b"certificate")
        assessment = self._assessment(self.doc_requirement)
        accepted = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(cv.pk), actor=self.beneficiary)
        rejected = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(certificate.pk), actor=self.beneficiary)
        self.assertEqual(accepted.decision, TrustedReuseDecisionCode.ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.LIBRARY_KIND_MATCH, accepted.reasons)
        self.assertEqual(rejected.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.KIND_MISMATCH, rejected.reasons)

    def test_unknown_freshness_and_explicit_age_window_are_distinct(self):
        _, unknown = self._asset_version()
        unknown_decision = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(unknown.pk), actor=self.beneficiary)
        self.assertEqual(unknown_decision.decision, TrustedReuseDecisionCode.UNKNOWN)
        self.assertIn(TrustedReuseReasonCode.FRESHNESS_UNKNOWN, unknown_decision.reasons)
        _, old = self._asset_version(issued_at=timezone.localdate() - timedelta(days=100), text=b"old")
        old_decision = evaluate_trusted_reuse(assessment=self._assessment(self.window_requirement), candidate=self._candidate(old.pk), actor=self.beneficiary)
        self.assertEqual(old_decision.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.TOO_OLD, old_decision.reasons)

    def test_expired_document_is_rejected(self):
        _, version = self._asset_version(issued_at=timezone.localdate() - timedelta(days=20), expires_at=timezone.localdate() - timedelta(days=1))
        decision = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(version.pk), actor=self.beneficiary)
        self.assertEqual(decision.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.EXPIRED, decision.reasons)

    def test_sensitive_and_restricted_require_confirmation(self):
        for sensitivity in (JourneyArtifactSensitivity.SENSITIVE, JourneyArtifactSensitivity.RESTRICTED):
            _, version = self._asset_version(sensitivity=sensitivity, expires_at=timezone.localdate() + timedelta(days=30), text=str(sensitivity).encode())
            decision = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(version.pk), actor=self.beneficiary)
            self.assertEqual(decision.decision, TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION)
            self.assertTrue(decision.confirmation_required)

    def test_subject_mismatch_and_source_not_allowed_are_explicit(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        forged = replace(self._candidate(version.pk), subject=ActionMemorySubject(ActionMemorySubjectType.PROFILE, str(self.other.pk)))
        mismatch = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=forged, actor=self.beneficiary)
        self.assertIn(TrustedReuseReasonCode.SUBJECT_MISMATCH, mismatch.reasons)
        proof = self._active_proof()
        rejected = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(proof.pk), actor=self.beneficiary)
        self.assertIn(TrustedReuseReasonCode.SOURCE_NOT_ALLOWED, rejected.reasons)

    def test_active_and_revoked_proof_are_distinguished(self):
        proof = self._active_proof()
        assessment = self._assessment(self.proof_requirement)
        active = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(proof.pk), actor=self.beneficiary)
        self.assertEqual(active.decision, TrustedReuseDecisionCode.ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.PROOF_TYPE_MATCH, active.reasons)
        revoke_proof(proof=proof, actor=self.curator, reason="q4")
        revoked = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(proof.pk), actor=self.beneficiary)
        self.assertEqual(revoked.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.PROOF_REVOKED, revoked.reasons)

    def test_library_apply_materializes_q2_snapshot_and_evidence_without_satisfaction(self):
        asset, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        source_hash = version.content_hash
        result = apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk)
        use = PersonalAssetUse.objects.get(asset_version=version)
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        self.assertEqual(use.journey_artifact_id, evidence.artifact_id)
        self.assertEqual(evidence.artifact.journey_id, self.journey.pk)
        self.assertEqual(evidence.artifact.content_hash, source_hash)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, RequirementAssessmentState.UNASSESSED)
        version.refresh_from_db()
        self.assertEqual(version.content_hash, source_hash)
        self.assertIsNone(asset.archived_at)

    def test_same_apply_is_idempotent(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        first = apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk)
        second = apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk)
        self.assertEqual(first.journey_artifact_id, second.journey_artifact_id)
        self.assertEqual(first.evidence_id, second.evidence_id)
        self.assertEqual(PersonalAssetUse.objects.filter(asset_version=version).count(), 1)

    def test_historical_artifact_goes_through_library_then_new_journey_artifact(self):
        old = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE)
        source = create_artifact(journey=old, uploaded_file=pdf_upload(b"history"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CERTIFICATE, title="Certificat")
        result = apply_trusted_reuse(assessment=self._assessment(self.history_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.JOURNEY_ARTIFACT, candidate_source_id=source.pk)
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        saved = PersonalAssetVersion.objects.get(pk=result.source_asset_version_id)
        self.assertNotEqual(evidence.artifact_id, source.pk)
        self.assertEqual(saved.source_journey_artifact_id, source.pk)
        self.assertEqual(evidence.artifact.journey_id, self.journey.pk)
        self.assertEqual(evidence.artifact.content_hash, source.content_hash)
        self.assertEqual(evidence.artifact.personal_asset_use.asset_version_id, saved.pk)

    def test_sensitive_apply_has_no_transmission_before_confirmation(self):
        _, version = self._asset_version(sensitivity=JourneyArtifactSensitivity.SENSITIVE, expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk, confirmed=False)
        self.assertEqual(self.journey.artifacts.count(), 0)
        self.assertFalse(ServiceRequirementEvidence.objects.filter(assessment=assessment).exists())
        apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk, confirmed=True)
        self.assertEqual(self.journey.artifacts.count(), 1)

    def test_archive_and_new_version_are_revalidated_at_apply(self):
        asset, archived_version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        self._candidate(archived_version.pk)
        archive_personal_asset(actor=self.beneficiary, asset=asset)
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(assessment=self._assessment(self.doc_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=archived_version.pk)
        asset2, v1 = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30), text=b"v1")
        self._candidate(v1.pk)
        create_personal_asset_version(actor=self.beneficiary, asset=asset2, uploaded_file=pdf_upload(b"v2"), expires_at=timezone.localdate() + timedelta(days=30))
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(assessment=self._assessment(self.doc_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=v1.pk)

    def test_expiration_assessment_completion_and_closed_journey_are_revalidated(self):
        _, expiring = self._asset_version(issued_at=timezone.localdate() - timedelta(days=5), expires_at=timezone.localdate() - timedelta(days=1), text=b"expiring")
        preview_at = timezone.now() - timedelta(days=2)
        preview = evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(expiring.pk, observed_at=preview_at), actor=self.beneficiary, observed_at=preview_at)
        self.assertTrue(preview.acceptable)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(assessment=self._assessment(self.doc_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=expiring.pk)
        _, finished = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30), text=b"finished")
        done = assess_requirement(assessment=self._assessment(self.doc_requirement), actor=self.manager, status=RequirementAssessmentState.SATISFIED)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(assessment=done, actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=finished.pk)
        self.journey.__class__.objects.filter(pk=self.journey.pk).update(status=JourneyStatus.CANCELLED)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(assessment=self._assessment(self.window_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=finished.pk)

    def test_revoked_proof_after_preview_cannot_apply_and_leaves_no_mutation(self):
        proof = self._active_proof()
        assessment = self._assessment(self.proof_requirement)
        self.assertTrue(evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(proof.pk), actor=self.beneficiary).acceptable)
        revoke_proof(proof=proof, actor=self.curator, reason="after-preview")
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(assessment=assessment, actor=self.beneficiary, candidate_source=ActionMemorySource.PROOF, candidate_source_id=proof.pk)
        self.assertFalse(ServiceRequirementEvidence.objects.filter(assessment=assessment).exists())
        self.assertEqual(self.journey.artifacts.count(), 0)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, RequirementAssessmentState.UNASSESSED)

    def test_anonymous_foreign_controller_and_cross_journey_idor_are_denied(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        with self.assertRaises(PermissionDenied):
            evaluate_trusted_reuse(assessment=self._assessment(self.doc_requirement), candidate=self._candidate(version.pk), actor=AnonymousUser())
        _, foreign = self._asset_version(controller=self.other, subject=self.beneficiary, expires_at=timezone.localdate() + timedelta(days=30), text=b"foreign")
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(assessment=self._assessment(self.doc_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=foreign.pk)
        collaborator = User.objects.create_user(username="q4-collaborator", email="q4-collaborator@example.test", password="x")
        grant_activity_role(profile=collaborator, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR)
        assign_journey(journey=self.journey, profile=collaborator, responsibility=JourneyAssignmentResponsibility.FACILITATOR, assigned_by=self.manager)
        private_old = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE)
        private_artifact = create_artifact(journey=private_old, uploaded_file=pdf_upload(b"private"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CERTIFICATE, title="Privé", sensitivity=JourneyArtifactSensitivity.RESTRICTED)
        visible_ids = {item.source_id for item in action_memory_for_journey(actor=collaborator, journey=self.journey)}
        self.assertNotIn(str(private_artifact.pk), visible_ids)
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(assessment=self._assessment(self.history_requirement), actor=collaborator, candidate_source=ActionMemorySource.JOURNEY_ARTIFACT, candidate_source_id=private_artifact.pk, confirmed=True)

    def test_external_beneficiary_controller_and_subject_are_preserved(self):
        external = ExternalBeneficiary.objects.create(display_name="External Q4", created_by=self.manager)
        journey = create_service_journey(service=self.service, initiated_by=self.manager, external_beneficiary=external, opportunity=self.opportunity)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        assessment = journey.service_context.requirement_assessments.get(requirement=self.doc_requirement)
        _, version = self._asset_version(controller=self.manager, external_subject=external, expires_at=timezone.localdate() + timedelta(days=30), text=b"external")
        result = apply_trusted_reuse(assessment=assessment, actor=self.manager, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=version.pk)
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        self.assertEqual(evidence.artifact.journey_id, journey.pk)
        self.assertEqual(evidence.artifact.personal_asset_use.asset_version_id, version.pk)

    def test_q2_snapshot_remains_v1_after_library_v2(self):
        asset, v1 = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30), text=b"immutable-v1")
        result = apply_trusted_reuse(assessment=self._assessment(self.doc_requirement), actor=self.beneficiary, candidate_source=ActionMemorySource.LIBRARY, candidate_source_id=v1.pk)
        artifact_hash = ServiceRequirementEvidence.objects.get(pk=result.evidence_id).artifact.content_hash
        v2 = create_personal_asset_version(actor=self.beneficiary, asset=asset, uploaded_file=pdf_upload(b"immutable-v2"), expires_at=timezone.localdate() + timedelta(days=30))
        self.assertNotEqual(v1.content_hash, v2.content_hash)
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        self.assertEqual(evidence.artifact.content_hash, artifact_hash)
        self.assertEqual(evidence.artifact.personal_asset_use.asset_version_id, v1.pk)

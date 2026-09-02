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
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyAssignmentResponsibility,
)
from journeys.collaboration_services import assign_journey, create_artifact
from journeys.models import ExternalBeneficiary, JourneyStatus, WorkflowKind
from journeys.services import create_journey
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import (
    add_requirement,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
)
from personal_assets.action_memory import ActionMemorySource, ActionMemorySubject, ActionMemorySubjectType, action_memory_for_journey
from personal_assets.models import PersonalAssetUse, PersonalAssetVersion
from personal_assets.services import archive_personal_asset, create_personal_asset, create_personal_asset_version
from requirements.contracts import RequirementAssessmentState
from requirements.models import RequirementReusePolicy, RequirementReuseSource
from requirements.trusted_reuse import TrustedReuseDecisionCode, TrustedReuseReasonCode
from trust.models import Proof, ProofStatus, ProofType
from trust.services import revoke_proof

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementEvidence
from .requirement_services import assess_requirement
from .services import create_service_details, create_service_journey
from .trusted_reuse import apply_trusted_reuse, evaluate_trusted_reuse


User = get_user_model()


def pdf_upload(text=b"q4-trusted-reuse"):
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n" + text + b"\n%%EOF",
        content_type="application/pdf",
    )


class TrustedReuseQ4Tests(TestCase):
    def setUp(self):
        self.curator = User.objects.create_user(username="q4-curator", password="x", is_staff=True, is_superuser=True)
        self.manager = User.objects.create_user(username="q4-manager", password="x")
        self.beneficiary = User.objects.create_user(username="q4-beneficiary", password="x")
        self.other = User.objects.create_user(username="q4-other", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Q4 Trusted Reuse")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.service = create_service_details(
            activity=self.activity,
            actor=self.manager,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
            allows_external_beneficiary=True,
        )
        self.opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.SCHOLARSHIP)
        self.revision = create_opportunity_revision(
            opportunity=self.opportunity,
            actor=self.curator,
            title="Q4 opportunity",
            issuer_name="Q4 issuer",
            timezone_name="UTC",
        )
        create_opportunity_source(
            opportunity=self.opportunity,
            actor=self.curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Q4 official",
            url=f"https://example.test/q4/{self.opportunity.pk}",
            is_primary=True,
            verified=True,
        )
        self.doc_requirement = add_requirement(
            revision=self.revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="Document structuré",
            position=10,
        )
        self.window_requirement = add_requirement(
            revision=self.revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="Document récent",
            position=20,
        )
        self.history_requirement = add_requirement(
            revision=self.revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="Certificat historique",
            position=30,
        )
        self.proof_requirement = add_requirement(
            revision=self.revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.ELIGIBILITY,
            title="Service déjà accompli",
            position=40,
        )
        self.no_policy_requirement = add_requirement(
            revision=self.revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="Cas sans policy",
            position=50,
        )
        RequirementReusePolicy.objects.create(
            requirement=self.doc_requirement,
            key="library-cv",
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind=JourneyArtifactKind.CV,
            require_not_expired=True,
            allow_sensitive_with_confirmation=True,
            allow_restricted_with_confirmation=True,
        )
        RequirementReusePolicy.objects.create(
            requirement=self.window_requirement,
            key="recent-cv",
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind=JourneyArtifactKind.CV,
            require_not_expired=False,
            max_age_days=90,
        )
        RequirementReusePolicy.objects.create(
            requirement=self.history_requirement,
            key="historical-certificate",
            source_type=RequirementReuseSource.JOURNEY_ARTIFACT,
            artifact_kind=JourneyArtifactKind.CERTIFICATE,
            require_not_expired=False,
        )
        RequirementReusePolicy.objects.create(
            requirement=self.proof_requirement,
            key="service-completed",
            source_type=RequirementReuseSource.PROOF,
            proof_type=ProofType.SERVICE_COMPLETED,
        )
        publish_opportunity_revision(opportunity=self.opportunity, revision=self.revision, actor=self.curator)
        self.journey = create_service_journey(
            service=self.service,
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            opportunity=self.opportunity,
        )
        self.assessments = {
            item.requirement_id: item
            for item in self.journey.service_context.requirement_assessments.select_related("requirement")
        }

    def _assessment(self, requirement):
        return self.assessments[requirement.pk]

    def _asset_version(
        self,
        *,
        controller=None,
        subject=None,
        kind=JourneyArtifactKind.CV,
        sensitivity=JourneyArtifactSensitivity.NORMAL,
        issued_at=None,
        expires_at=None,
        text=b"library-v1",
    ):
        controller = controller or self.beneficiary
        subject = subject or self.beneficiary
        asset = create_personal_asset(
            controller=controller,
            subject_profile=subject,
            title="Document Q4",
            kind=kind,
            sensitivity=sensitivity,
        )
        version = create_personal_asset_version(
            actor=controller,
            asset=asset,
            uploaded_file=pdf_upload(text),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return asset, version

    def _candidate(self, source_id, *, actor=None, journey=None, observed_at=None):
        actor = actor or self.beneficiary
        journey = journey or self.journey
        return next(
            item
            for item in action_memory_for_journey(actor=actor, journey=journey, observed_at=observed_at)
            if item.source_id == str(source_id)
        )

    def _active_proof(self):
        old = create_journey(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.FULFILLED,
        )
        return Proof.objects.create(
            subject_profile=self.beneficiary,
            journey=old,
            proof_type=ProofType.SERVICE_COMPLETED,
        )

    def test_no_policy_is_unknown_and_does_not_mutate_assessment(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.no_policy_requirement)
        candidate = self._candidate(version.pk)
        before = (assessment.status, ServiceRequirementEvidence.objects.count(), self.journey.artifacts.count())

        decision = evaluate_trusted_reuse(assessment=assessment, candidate=candidate, actor=self.beneficiary)

        self.assertEqual(decision.decision, TrustedReuseDecisionCode.UNKNOWN)
        self.assertIn(TrustedReuseReasonCode.NO_POLICY, decision.reasons)
        assessment.refresh_from_db()
        self.assertEqual(before, (assessment.status, ServiceRequirementEvidence.objects.count(), self.journey.artifacts.count()))

    def test_exact_kind_is_acceptable_and_wrong_kind_is_not(self):
        _, cv = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        _, certificate = self._asset_version(
            kind=JourneyArtifactKind.CERTIFICATE,
            expires_at=timezone.localdate() + timedelta(days=30),
            text=b"certificate",
        )
        assessment = self._assessment(self.doc_requirement)

        accepted = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(cv.pk), actor=self.beneficiary)
        rejected = evaluate_trusted_reuse(assessment=assessment, candidate=self._candidate(certificate.pk), actor=self.beneficiary)

        self.assertEqual(accepted.decision, TrustedReuseDecisionCode.ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.LIBRARY_KIND_MATCH, accepted.reasons)
        self.assertEqual(rejected.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.KIND_MISMATCH, rejected.reasons)

    def test_freshness_unknown_and_explicit_max_age_are_distinct(self):
        _, unknown = self._asset_version()
        unknown_decision = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement),
            candidate=self._candidate(unknown.pk),
            actor=self.beneficiary,
        )
        self.assertEqual(unknown_decision.decision, TrustedReuseDecisionCode.UNKNOWN)
        self.assertIn(TrustedReuseReasonCode.FRESHNESS_UNKNOWN, unknown_decision.reasons)

        _, old = self._asset_version(
            issued_at=timezone.localdate() - timedelta(days=100),
            text=b"old-cv",
        )
        old_decision = evaluate_trusted_reuse(
            assessment=self._assessment(self.window_requirement),
            candidate=self._candidate(old.pk),
            actor=self.beneficiary,
        )
        self.assertEqual(old_decision.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.TOO_OLD, old_decision.reasons)

    def test_expired_document_is_not_acceptable(self):
        _, version = self._asset_version(
            issued_at=timezone.localdate() - timedelta(days=20),
            expires_at=timezone.localdate() - timedelta(days=1),
        )
        decision = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement),
            candidate=self._candidate(version.pk),
            actor=self.beneficiary,
        )
        self.assertEqual(decision.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.EXPIRED, decision.reasons)

    def test_sensitive_and_restricted_require_explicit_confirmation(self):
        for sensitivity in (JourneyArtifactSensitivity.SENSITIVE, JourneyArtifactSensitivity.RESTRICTED):
            _, version = self._asset_version(
                sensitivity=sensitivity,
                expires_at=timezone.localdate() + timedelta(days=30),
                text=sensitivity.encode(),
            )
            decision = evaluate_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                candidate=self._candidate(version.pk),
                actor=self.beneficiary,
            )
            self.assertEqual(decision.decision, TrustedReuseDecisionCode.ACCEPTABLE_WITH_CONFIRMATION)
            self.assertTrue(decision.confirmation_required)

    def test_subject_mismatch_and_disallowed_source_are_explicit(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        candidate = self._candidate(version.pk)
        forged = replace(
            candidate,
            subject=ActionMemorySubject(ActionMemorySubjectType.PROFILE, str(self.other.pk)),
        )
        mismatch = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement), candidate=forged, actor=self.beneficiary
        )
        self.assertEqual(mismatch.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.SUBJECT_MISMATCH, mismatch.reasons)

        proof = self._active_proof()
        proof_candidate = self._candidate(proof.pk)
        source_rejected = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement), candidate=proof_candidate, actor=self.beneficiary
        )
        self.assertEqual(source_rejected.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.SOURCE_NOT_ALLOWED, source_rejected.reasons)

    def test_active_proof_can_be_accepted_but_revoked_proof_cannot(self):
        proof = self._active_proof()
        assessment = self._assessment(self.proof_requirement)
        active = evaluate_trusted_reuse(
            assessment=assessment,
            candidate=self._candidate(proof.pk),
            actor=self.beneficiary,
        )
        self.assertEqual(active.decision, TrustedReuseDecisionCode.ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.PROOF_TYPE_MATCH, active.reasons)

        revoke_proof(proof=proof, actor=self.curator, reason="q4-test")
        revoked = evaluate_trusted_reuse(
            assessment=assessment,
            candidate=self._candidate(proof.pk),
            actor=self.beneficiary,
        )
        self.assertEqual(revoked.decision, TrustedReuseDecisionCode.NOT_ACCEPTABLE)
        self.assertIn(TrustedReuseReasonCode.PROOF_REVOKED, revoked.reasons)

    def test_library_apply_uses_q2_snapshot_and_canonical_evidence_without_satisfaction(self):
        asset, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        source_hash = version.content_hash

        result = apply_trusted_reuse(
            assessment=assessment,
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.LIBRARY,
            candidate_source_id=version.pk,
        )

        use = PersonalAssetUse.objects.get(asset_version=version)
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        self.assertEqual(use.journey_artifact_id, evidence.artifact_id)
        self.assertEqual(evidence.artifact.journey_id, self.journey.pk)
        self.assertEqual(evidence.artifact.content_hash, source_hash)
        self.assertEqual(evidence.status, "submitted")
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, RequirementAssessmentState.UNASSESSED)
        version.refresh_from_db()
        self.assertEqual(version.content_hash, source_hash)
        self.assertEqual(asset.archived_at, None)

    def test_apply_is_idempotent_for_same_source_requirement_and_journey(self):
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
        self.assertEqual(first.journey_artifact_id, second.journey_artifact_id)
        self.assertEqual(first.evidence_id, second.evidence_id)
        self.assertEqual(PersonalAssetUse.objects.filter(asset_version=version).count(), 1)

    def test_historical_artifact_never_links_directly_across_journeys(self):
        old = create_journey(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        source = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"historical-certificate"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Certificat historique",
        )
        result = apply_trusted_reuse(
            assessment=self._assessment(self.history_requirement),
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.JOURNEY_ARTIFACT,
            candidate_source_id=source.pk,
        )
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        saved = PersonalAssetVersion.objects.get(pk=result.source_asset_version_id)
        self.assertNotEqual(evidence.artifact_id, source.pk)
        self.assertEqual(evidence.artifact.journey_id, self.journey.pk)
        self.assertEqual(saved.source_journey_artifact_id, source.pk)
        self.assertEqual(evidence.artifact.personal_asset_use.asset_version_id, saved.pk)
        self.assertEqual(evidence.artifact.content_hash, source.content_hash)

    def test_sensitive_apply_does_not_transmit_until_confirmation(self):
        _, version = self._asset_version(
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
            expires_at=timezone.localdate() + timedelta(days=30),
        )
        assessment = self._assessment(self.doc_requirement)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(
                assessment=assessment,
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=version.pk,
                confirmed=False,
            )
        self.assertEqual(self.journey.artifacts.count(), 0)
        self.assertEqual(ServiceRequirementEvidence.objects.filter(assessment=assessment).count(), 0)

        apply_trusted_reuse(
            assessment=assessment,
            actor=self.beneficiary,
            candidate_source=ActionMemorySource.LIBRARY,
            candidate_source_id=version.pk,
            confirmed=True,
        )
        self.assertEqual(self.journey.artifacts.count(), 1)

    def test_toctou_archive_new_version_expiration_and_finished_requirement_are_revalidated(self):
        asset, archived_version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        self._candidate(archived_version.pk)
        archive_personal_asset(actor=self.beneficiary, asset=asset)
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=archived_version.pk,
            )

        asset2, old_version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30), text=b"old-version")
        self._candidate(old_version.pk)
        create_personal_asset_version(
            actor=self.beneficiary,
            asset=asset2,
            uploaded_file=pdf_upload(b"new-version"),
            expires_at=timezone.localdate() + timedelta(days=30),
        )
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=old_version.pk,
            )

        _, expiring = self._asset_version(
            issued_at=timezone.localdate() - timedelta(days=5),
            expires_at=timezone.localdate() - timedelta(days=1),
            text=b"expiring",
        )
        preview_at = timezone.now() - timedelta(days=2)
        preview_candidate = self._candidate(expiring.pk, observed_at=preview_at)
        preview = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement),
            candidate=preview_candidate,
            actor=self.beneficiary,
            observed_at=preview_at,
        )
        self.assertTrue(preview.acceptable)
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=expiring.pk,
            )

        _, current = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30), text=b"finished")
        assessment = assess_requirement(
            assessment=self._assessment(self.doc_requirement),
            actor=self.manager,
            status=RequirementAssessmentState.SATISFIED,
        )
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(
                assessment=assessment,
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=current.pk,
            )

    def test_revoked_proof_between_preview_and_apply_leaves_no_residual_mutation(self):
        proof = self._active_proof()
        assessment = self._assessment(self.proof_requirement)
        preview = evaluate_trusted_reuse(
            assessment=assessment,
            candidate=self._candidate(proof.pk),
            actor=self.beneficiary,
        )
        self.assertTrue(preview.acceptable)
        revoke_proof(proof=proof, actor=self.curator, reason="revoked-after-preview")
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(
                assessment=assessment,
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.PROOF,
                candidate_source_id=proof.pk,
            )
        self.assertEqual(ServiceRequirementEvidence.objects.filter(assessment=assessment).count(), 0)
        self.assertEqual(self.journey.artifacts.count(), 0)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, RequirementAssessmentState.UNASSESSED)

    def test_anonymous_and_forged_controller_source_are_denied(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        with self.assertRaises(PermissionDenied):
            evaluate_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                candidate=self._candidate(version.pk),
                actor=AnonymousUser(),
            )

        _, foreign = self._asset_version(
            controller=self.other,
            subject=self.beneficiary,
            expires_at=timezone.localdate() + timedelta(days=30),
            text=b"foreign-controller",
        )
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=foreign.pk,
            )

    def test_closed_journey_is_rejected_before_transfer(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        self.journey.__class__.objects.filter(pk=self.journey.pk).update(status=JourneyStatus.CANCELLED)
        self.journey.refresh_from_db()
        with self.assertRaises(ValidationError):
            apply_trusted_reuse(
                assessment=self._assessment(self.doc_requirement),
                actor=self.beneficiary,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=version.pk,
            )
        self.assertEqual(self.journey.artifacts.count(), 0)

    def test_cross_journey_forged_historical_artifact_is_not_disclosed_or_applied(self):
        collaborator = User.objects.create_user(username="q4-collaborator", password="x")
        grant_activity_role(profile=collaborator, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR)
        assign_journey(
            journey=self.journey,
            profile=collaborator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )
        private_old = create_journey(
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        private_artifact = create_artifact(
            journey=private_old,
            uploaded_file=pdf_upload(b"private-old"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Privé",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        visible_ids = {item.source_id for item in action_memory_for_journey(actor=collaborator, journey=self.journey)}
        self.assertNotIn(str(private_artifact.pk), visible_ids)
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(
                assessment=self._assessment(self.history_requirement),
                actor=collaborator,
                candidate_source=ActionMemorySource.JOURNEY_ARTIFACT,
                candidate_source_id=private_artifact.pk,
                confirmed=True,
            )

    def test_external_beneficiary_controller_can_apply_only_with_journey_authority(self):
        external = ExternalBeneficiary.objects.create(display_name="External Q4", created_by=self.manager)
        journey = create_service_journey(
            service=self.service,
            initiated_by=self.manager,
            external_beneficiary=external,
            opportunity=self.opportunity,
        )
        assign_journey(
            journey=journey,
            profile=self.manager,
            responsibility=JourneyAssignmentResponsibility.LEAD,
            is_primary=True,
            assigned_by=self.manager,
        )
        assessment = journey.service_context.requirement_assessments.get(requirement=self.doc_requirement)
        asset = create_personal_asset(
            controller=self.manager,
            subject_external_beneficiary=external,
            title="CV externe",
            kind=JourneyArtifactKind.CV,
        )
        version = create_personal_asset_version(
            actor=self.manager,
            asset=asset,
            uploaded_file=pdf_upload(b"external"),
            expires_at=timezone.localdate() + timedelta(days=30),
        )
        result = apply_trusted_reuse(
            assessment=assessment,
            actor=self.manager,
            candidate_source=ActionMemorySource.LIBRARY,
            candidate_source_id=version.pk,
        )
        evidence = ServiceRequirementEvidence.objects.get(pk=result.evidence_id)
        self.assertEqual(evidence.artifact.journey_id, journey.pk)
        self.assertEqual(evidence.artifact.personal_asset_use.asset_version_id, version.pk)

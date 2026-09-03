import inspect
from dataclasses import fields
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.beneficiary_services import create_journey_for_holder
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
)
from journeys.collaboration_services import create_artifact
from journeys.models import ExternalBeneficiary, JourneyStatus, WorkflowKind
from journeys.services import create_journey
from journeys.storage import private_artifact_storage
from opportunities.models import OpportunityRequirement
from services.models import ServiceRequirementAssessment, ServiceRequirementEvidence
from trust.models import Proof, ProofStatus, ProofType

from .action_memory import (
    ActionMemoryAction,
    ActionMemoryCandidate,
    ActionMemoryFreshness,
    ActionMemoryMaterializationPath,
    ActionMemoryProvenanceCode,
    ActionMemoryReasonCode,
    ActionMemorySource,
    ActionMemorySubjectType,
    action_memory_for_journey,
)
from .models import PersonalAsset, PersonalAssetUse, PersonalAssetVersion
from .services import (
    archive_personal_asset,
    create_personal_asset,
    create_personal_asset_version,
    save_journey_artifact_to_library,
)


User = get_user_model()


def pdf_upload(text=b"q3-action-memory"):
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n" + text + b"\n%%EOF",
        content_type="application/pdf",
    )


class ActionMemoryQ3Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="q3-owner", email="q3-owner@example.test", password="x")
        self.other = User.objects.create_user(username="q3-other", email="q3-other@example.test", password="x")
        self.subject = User.objects.create_user(username="q3-subject", email="q3-subject@example.test", password="x")
        self.operator = User.objects.create_user(username="q3-operator", email="q3-operator@example.test", password="x")
        self.activity = Activity.objects.create(
            owner_profile=self.operator,
            created_by=self.operator,
            title="Q3 Action Memory",
        )
        self.current = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )

    def _asset(self, *, controller=None, subject=None, title="CV", kind=JourneyArtifactKind.CV, sensitivity=JourneyArtifactSensitivity.NORMAL):
        return create_personal_asset(
            controller=controller or self.owner,
            subject_profile=subject or self.owner,
            title=title,
            kind=kind,
            sensitivity=sensitivity,
        )

    def _version(self, asset, *, text=b"version", issued_at=None, expires_at=None):
        return create_personal_asset_version(
            actor=asset.controller,
            asset=asset,
            uploaded_file=pdf_upload(text),
            issued_at=issued_at,
            expires_at=expires_at,
        )

    def _old_journey(self, *, beneficiary=None, status=JourneyStatus.DRAFT):
        return create_journey(
            initiated_by=beneficiary or self.owner,
            beneficiary=beneficiary or self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            status=status,
        )

    def _collaborator_journey(self, *, beneficiary, assign_current=True):
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        journey = create_journey(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        if assign_current:
            JourneyAssignment.objects.create(
                journey=journey,
                profile=self.owner,
                responsibility=JourneyAssignmentResponsibility.FACILITATOR,
                assigned_by=self.operator,
            )
        return journey

    def test_library_is_controller_scoped_and_archived_assets_are_not_current_candidates(self):
        visible = self._asset(title="Visible")
        visible_version = self._version(visible)
        hidden = self._asset(controller=self.other, subject=self.owner, title="Other controller")
        self._version(hidden)
        archived = self._asset(title="Archive")
        archived_version = self._version(archived)
        archive_personal_asset(actor=self.owner, asset=archived)

        candidates = action_memory_for_journey(actor=self.owner, journey=self.current)
        ids = {candidate.source_id for candidate in candidates if candidate.source == ActionMemorySource.LIBRARY}

        self.assertIn(str(visible_version.pk), ids)
        self.assertNotIn(str(archived_version.pk), ids)
        self.assertFalse(any(candidate.title == "Other controller" for candidate in candidates))

    def test_controller_and_subject_remain_distinct_authorization_axes(self):
        current_for_subject = self._collaborator_journey(beneficiary=self.subject)
        asset = self._asset(subject=self.subject, title="Document du sujet")
        version = self._version(asset)

        controller_candidates = action_memory_for_journey(actor=self.owner, journey=current_for_subject)
        subject_candidates = action_memory_for_journey(actor=self.subject, journey=current_for_subject)

        candidate = next(item for item in controller_candidates if item.source_id == str(version.pk))
        self.assertEqual(candidate.subject.subject_type, ActionMemorySubjectType.PROFILE)
        self.assertEqual(candidate.subject.source_id, str(self.subject.pk))
        self.assertEqual(candidate.action, ActionMemoryAction.USE_IN_JOURNEY)
        self.assertFalse(any(item.source_id == str(version.pk) for item in subject_candidates))

    def test_external_beneficiary_is_scoped_by_exact_subject_and_controller(self):
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        external = ExternalBeneficiary.objects.create(display_name="Bénéficiaire externe", created_by=self.owner)
        journey = create_journey_for_holder(
            initiated_by=self.owner,
            external_beneficiary=external,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        JourneyAssignment.objects.create(
            journey=journey,
            profile=self.owner,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.operator,
        )
        asset = create_personal_asset(
            controller=self.owner,
            subject_external_beneficiary=external,
            title="Acte externe",
            kind=JourneyArtifactKind.CERTIFICATE,
        )
        version = self._version(asset)

        candidates = action_memory_for_journey(actor=self.owner, journey=journey)
        candidate = next(item for item in candidates if item.source_id == str(version.pk))

        self.assertEqual(candidate.subject.subject_type, ActionMemorySubjectType.EXTERNAL_BENEFICIARY)
        self.assertEqual(candidate.subject.source_id, str(external.pk))
        self.assertEqual(candidate.action, ActionMemoryAction.USE_IN_JOURNEY)

    def test_latest_library_version_is_selected_without_rewriting_history(self):
        asset = self._asset(title="Versionné")
        first = self._version(asset, text=b"first")
        second = self._version(asset, text=b"second")

        candidates = action_memory_for_journey(actor=self.owner, journey=self.current)
        library = [item for item in candidates if item.source == ActionMemorySource.LIBRARY and item.parent_source_id == str(asset.pk)]

        self.assertEqual(len(library), 1)
        self.assertEqual(library[0].source_id, str(second.pk))
        self.assertEqual(library[0].source_version, 2)
        first.refresh_from_db()
        self.assertEqual(first.version, 1)
        self.assertIsNone(first.supersedes_id)
        self.assertEqual(second.supersedes_id, first.pk)

    def test_freshness_uses_only_explicit_expiration_facts(self):
        expired_asset = self._asset(title="Expiré")
        expired = self._version(
            expired_asset,
            expires_at=timezone.localdate() - timedelta(days=1),
        )
        unknown_asset = self._asset(title="Sans politique")
        unknown = self._version(unknown_asset)
        current_asset = self._asset(title="Non expiré")
        current = self._version(
            current_asset,
            expires_at=timezone.localdate() + timedelta(days=1),
        )

        candidates = {item.source_id: item for item in action_memory_for_journey(actor=self.owner, journey=self.current)}

        self.assertEqual(candidates[str(expired.pk)].freshness, ActionMemoryFreshness.EXPIRED)
        self.assertEqual(candidates[str(expired.pk)].action, ActionMemoryAction.REVIEW_LIBRARY)
        self.assertIn(ActionMemoryReasonCode.LIBRARY_EXPIRED, candidates[str(expired.pk)].reasons)
        self.assertEqual(candidates[str(unknown.pk)].freshness, ActionMemoryFreshness.UNKNOWN)
        self.assertEqual(candidates[str(current.pk)].freshness, ActionMemoryFreshness.NOT_EXPIRED)

    def test_sensitive_and_restricted_library_candidates_require_confirmation(self):
        sensitive = self._asset(title="Sensible", sensitivity=JourneyArtifactSensitivity.SENSITIVE)
        sensitive_version = self._version(sensitive)
        restricted = self._asset(title="Restreint", sensitivity=JourneyArtifactSensitivity.RESTRICTED)
        restricted_version = self._version(restricted)

        candidates = {item.source_id: item for item in action_memory_for_journey(actor=self.owner, journey=self.current)}

        for source_id in (str(sensitive_version.pk), str(restricted_version.pk)):
            self.assertTrue(candidates[source_id].confirmation_required)
            self.assertIn(ActionMemoryReasonCode.CONFIRMATION_REQUIRED, candidates[source_id].reasons)

    def test_action_memory_never_opens_file_payloads(self):
        asset = self._asset(title="Métadonnées seulement")
        self._version(asset)

        with mock.patch.object(private_artifact_storage, "open", side_effect=AssertionError("payload read")):
            candidates = action_memory_for_journey(actor=self.owner, journey=self.current)

        self.assertTrue(candidates)

    def test_accessible_historical_artifact_is_detected_with_provenance_without_transfer(self):
        old = self._old_journey()
        artifact = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"old-certificate"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Certificat ancien",
        )
        before_current_artifacts = self.current.artifacts.count()

        candidates = action_memory_for_journey(actor=self.owner, journey=self.current)
        candidate = next(item for item in candidates if item.source_id == str(artifact.pk))

        self.assertEqual(candidate.source, ActionMemorySource.JOURNEY_ARTIFACT)
        self.assertEqual(candidate.provenance.code, ActionMemoryProvenanceCode.JOURNEY)
        self.assertEqual(candidate.provenance.journey_id, str(old.pk))
        self.assertEqual(candidate.action, ActionMemoryAction.SAVE_TO_LIBRARY)
        self.assertEqual(candidate.materialization_path, ActionMemoryMaterializationPath.JOURNEY_ARTIFACT_TO_PERSONAL_ASSET)
        self.assertEqual(self.current.artifacts.count(), before_current_artifacts)

    def test_new_journey_collaborator_does_not_gain_old_journey_history(self):
        current_for_subject = self._collaborator_journey(beneficiary=self.subject)
        old = self._old_journey(beneficiary=self.subject)
        artifact = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"private-old"),
            uploaded_by=self.subject,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Secret ancienne Journey",
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )

        candidates = action_memory_for_journey(actor=self.owner, journey=current_for_subject)
        self.assertFalse(any(item.source_id == str(artifact.pk) for item in candidates))

        JourneyAssignment.objects.create(
            journey=old,
            profile=self.owner,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            assigned_by=self.operator,
        )
        candidates = action_memory_for_journey(actor=self.owner, journey=current_for_subject)
        candidate = next(item for item in candidates if item.source_id == str(artifact.pk))
        self.assertEqual(candidate.action, ActionMemoryAction.NONE)
        self.assertTrue(candidate.confirmation_required)

    def test_current_journey_idor_is_denied_before_history_is_read(self):
        with self.assertRaises(PermissionDenied):
            action_memory_for_journey(actor=self.other, journey=self.current)

    def test_restricted_historical_artifact_is_qualified_and_confirmation_is_required(self):
        old = self._old_journey()
        artifact = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"restricted-old"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Identité",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )

        candidate = next(
            item
            for item in action_memory_for_journey(actor=self.owner, journey=self.current)
            if item.source_id == str(artifact.pk)
        )

        self.assertEqual(candidate.sensitivity, JourneyArtifactSensitivity.RESTRICTED)
        self.assertTrue(candidate.confirmation_required)
        self.assertIn(ActionMemoryReasonCode.JOURNEY_RESTRICTED, candidate.reasons)

    def test_q2_provenance_and_hash_deduplicate_only_the_exact_snapshot(self):
        old = self._old_journey()
        artifact = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"same-payload"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="À conserver",
        )
        version = save_journey_artifact_to_library(actor=self.owner, journey_artifact=artifact)

        candidates = action_memory_for_journey(actor=self.owner, journey=self.current)
        same_payload = [item for item in candidates if item.content_hash == artifact.content_hash]

        self.assertEqual(len(same_payload), 1)
        self.assertEqual(same_payload[0].source, ActionMemorySource.LIBRARY)
        self.assertEqual(same_payload[0].source_id, str(version.pk))
        self.assertEqual(same_payload[0].provenance.code, ActionMemoryProvenanceCode.LIBRARY_FROM_JOURNEY)
        self.assertEqual(same_payload[0].provenance.related_source_id, str(artifact.pk))

    def test_proof_source_is_subject_scoped_and_revoked_is_never_active(self):
        active_journey = self._old_journey(status=JourneyStatus.FULFILLED)
        active = Proof.objects.create(
            subject_profile=self.owner,
            journey=active_journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
        )
        revoked_journey = self._old_journey(status=JourneyStatus.FULFILLED)
        revoked = Proof.objects.create(
            subject_profile=self.owner,
            journey=revoked_journey,
            proof_type=ProofType.SERVICE_COMPLETED,
            status=ProofStatus.REVOKED,
            revoked_at=timezone.now(),
        )
        other_journey = self._old_journey(beneficiary=self.subject, status=JourneyStatus.FULFILLED)
        public_other = Proof.objects.create(
            subject_profile=self.subject,
            journey=other_journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
            is_public=True,
        )

        candidates = action_memory_for_journey(actor=self.owner, journey=self.current)
        by_id = {item.source_id: item for item in candidates if item.source == ActionMemorySource.PROOF}

        self.assertIn(str(active.pk), by_id)
        self.assertIn(ActionMemoryReasonCode.PROOF_ACTIVE, by_id[str(active.pk)].reasons)
        self.assertEqual(by_id[str(active.pk)].action, ActionMemoryAction.VIEW_PROOF)
        self.assertIn(str(revoked.pk), by_id)
        self.assertIn(ActionMemoryReasonCode.PROOF_REVOKED, by_id[str(revoked.pk)].reasons)
        self.assertNotIn(ActionMemoryReasonCode.PROOF_ACTIVE, by_id[str(revoked.pk)].reasons)
        self.assertNotIn(str(public_other.pk), by_id)

    def test_public_proof_does_not_bypass_old_journey_authorization_for_collaborator(self):
        current_for_subject = self._collaborator_journey(beneficiary=self.subject)
        old = self._old_journey(beneficiary=self.subject, status=JourneyStatus.FULFILLED)
        proof = Proof.objects.create(
            subject_profile=self.subject,
            journey=old,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
            is_public=True,
        )

        candidates = action_memory_for_journey(actor=self.owner, journey=current_for_subject)
        self.assertFalse(any(item.source_id == str(proof.pk) for item in candidates))

    def test_contract_is_explainable_has_no_score_and_does_not_accept_requirement_input(self):
        field_names = {field.name for field in fields(ActionMemoryCandidate)}
        parameter_names = set(inspect.signature(action_memory_for_journey).parameters)
        reason_values = {reason.value for reason in ActionMemoryReasonCode}

        self.assertNotIn("score", field_names)
        self.assertNotIn("memory_score", field_names)
        self.assertNotIn("requirement", parameter_names)
        self.assertNotIn("accepted_for_requirement", reason_values)
        self.assertNotIn("requirement.satisfied", reason_values)

    def test_building_memory_does_not_mutate_owner_domain_state(self):
        asset = self._asset(title="Read only")
        self._version(asset)
        old = self._old_journey(status=JourneyStatus.FULFILLED)
        artifact = create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"read-only-artifact"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Artifact read only",
        )
        proof = Proof.objects.create(
            subject_profile=self.owner,
            journey=old,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
        )
        before = {
            PersonalAsset: PersonalAsset.objects.count(),
            PersonalAssetVersion: PersonalAssetVersion.objects.count(),
            PersonalAssetUse: PersonalAssetUse.objects.count(),
            JourneyArtifact: JourneyArtifact.objects.count(),
            Proof: Proof.objects.count(),
            OpportunityRequirement: OpportunityRequirement.objects.count(),
            ServiceRequirementAssessment: ServiceRequirementAssessment.objects.count(),
            ServiceRequirementEvidence: ServiceRequirementEvidence.objects.count(),
        }
        current_artifact_count = self.current.artifacts.count()

        action_memory_for_journey(actor=self.owner, journey=self.current)

        after = {model: model.objects.count() for model in before}
        self.assertEqual(after, before)
        self.assertEqual(self.current.artifacts.count(), current_artifact_count)
        artifact.refresh_from_db()
        proof.refresh_from_db()
        self.assertEqual(artifact.status, "draft")
        self.assertEqual(proof.status, ProofStatus.ACTIVE)

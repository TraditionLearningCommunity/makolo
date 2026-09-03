from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from access.models import Access
from activities.models import Activity
from authorization.constants import SystemRoleCode
from journeys.collaboration_models import JourneyArtifact, JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.models import Journey, WorkflowKind
from objectives.services import assign_dossier, create_dossier, grant_dossier_authority
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRequirement,
    OpportunityRequirementKind,
    OpportunityRevision,
)
from payments.models import Payment
from personal_assets.models import PersonalAsset, PersonalAssetUse, PersonalAssetVersion
from readiness.types import ReadinessStatus
from requirements.contracts import RequirementAssessmentState
from requirements.models import RequirementReuseApplication, RequirementReusePolicy, RequirementReuseSource
from requirements.trusted_reuse import TrustedReuseDecisionCode, TrustedReuseReasonCode
from services.models import ServiceRequirementAssessment, ServiceRequirementEvidence
from trust.models import Proof, ProofStatus, ProofType

from .prepared_start import PreparedRequirementState, prepared_start_for_revision, revalidate_prepared_start_revision


User = get_user_model()


class PreparedStartR1Tests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(username="r1-actor", email="r1-actor@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="r1-other", email="r1-other@example.test", password="StrongPass2026!")

    def _draft_revision(self, *, opportunity=None, title="Bourse Makolo"):
        opportunity = opportunity or Opportunity.objects.create(kind=OpportunityKind.SCHOLARSHIP, created_by=self.actor)
        return OpportunityRevision.objects.create(
            opportunity=opportunity,
            version=opportunity.revisions.count() + 1,
            title=title,
            issuer_name="Institution test",
            timezone="Africa/Lubumbashi",
            deadline_at=timezone.now() + timedelta(days=30),
            created_by=self.actor,
        )

    def _requirement(self, revision, *, title="CV", mandatory=True):
        return OpportunityRequirement.objects.create(
            revision=revision,
            kind=OpportunityRequirementKind.DOCUMENT,
            title=title,
            is_mandatory=mandatory,
            position=revision.requirements.count() + 1,
        )

    def _policy(
        self,
        requirement,
        *,
        source=RequirementReuseSource.LIBRARY,
        artifact_kind=JourneyArtifactKind.CV,
        proof_type="",
        require_not_expired=True,
        max_age_days=None,
        sensitive=False,
        restricted=False,
        human_review=False,
        key="r1-policy",
    ):
        return RequirementReusePolicy.objects.create(
            requirement=requirement,
            key=key,
            source_type=source,
            artifact_kind="" if source == RequirementReuseSource.PROOF else artifact_kind,
            proof_type=proof_type if source == RequirementReuseSource.PROOF else "",
            require_not_expired=require_not_expired,
            max_age_days=max_age_days,
            allow_sensitive_with_confirmation=sensitive,
            allow_restricted_with_confirmation=restricted,
            human_review_required=human_review,
        )

    def _publish(self, revision):
        published_at = timezone.now()
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=published_at)
        Opportunity.objects.filter(pk=revision.opportunity_id).update(
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            current_revision=revision,
            published_at=published_at,
        )
        revision.refresh_from_db()
        return revision

    def _library_version(
        self,
        *,
        subject=None,
        kind=JourneyArtifactKind.CV,
        sensitivity=JourneyArtifactSensitivity.NORMAL,
        issued_at=None,
        expires_at=None,
        title="CV principal",
    ):
        subject = subject or self.actor
        asset = PersonalAsset.objects.create(
            controller=self.actor,
            subject_profile=subject,
            kind=kind,
            title=title,
            sensitivity=sensitivity,
        )
        return PersonalAssetVersion.objects.create(
            asset=asset,
            version=1,
            file=SimpleUploadedFile("r1.pdf", b"%PDF-1.4\nr1"),
            mime_type="application/pdf",
            size=12,
            content_hash="a" * 64,
            issued_at=issued_at,
            expires_at=expires_at,
            created_by=self.actor,
        )

    def _proof(self, *, status=ProofStatus.ACTIVE, proof_type=ProofType.SERVICE_COMPLETED):
        activity = Activity.objects.create(owner_profile=self.actor, created_by=self.actor, title="Ancienne démarche")
        journey = Journey.objects.create(
            initiated_by=self.actor,
            beneficiary=self.actor,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
        )
        return Proof.objects.create(
            subject_profile=self.actor,
            journey=journey,
            proof_type=proof_type,
            status=status,
            issued_by=self.actor,
        )

    def test_library_candidate_can_make_exact_requirement_prepared_without_assessment(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision)
        self._policy(requirement, human_review=False)
        self._publish(revision)
        version = self._library_version(
            issued_at=timezone.localdate() - timedelta(days=20),
            expires_at=timezone.localdate() + timedelta(days=180),
        )

        result = prepared_start_for_revision(actor=self.actor, revision=revision)

        item = result.requirements[0]
        self.assertEqual(item.assessment_state, RequirementAssessmentState.UNASSESSED)
        self.assertEqual(item.preparation_state, PreparedRequirementState.READY)
        self.assertEqual(item.reuse_options[0].candidate_source_id, str(version.pk))
        self.assertEqual(item.reuse_options[0].decision, TrustedReuseDecisionCode.ACCEPTABLE)
        self.assertEqual(result.readiness.status, ReadinessStatus.READY)
        self.assertFalse(ServiceRequirementAssessment.objects.exists())
        self.assertFalse(RequirementReuseApplication.objects.exists())

    def test_confirmation_and_human_review_are_not_reported_as_requirement_satisfied(self):
        revision = self._draft_revision()
        sensitive_requirement = self._requirement(revision, title="CV sensible")
        review_requirement = self._requirement(revision, title="CV à revoir")
        self._policy(sensitive_requirement, sensitive=True, human_review=False, key="sensitive")
        self._policy(review_requirement, human_review=True, key="review")
        self._publish(revision)
        self._library_version(
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
            expires_at=timezone.localdate() + timedelta(days=90),
            title="CV sensible",
        )
        self._library_version(
            sensitivity=JourneyArtifactSensitivity.NORMAL,
            expires_at=timezone.localdate() + timedelta(days=90),
            title="CV normal",
        )

        result = prepared_start_for_revision(actor=self.actor, revision=revision)
        by_title = {item.title: item for item in result.requirements}

        self.assertEqual(by_title["CV sensible"].preparation_state, PreparedRequirementState.CONFIRMATION_REQUIRED)
        self.assertEqual(by_title["CV sensible"].assessment_state, RequirementAssessmentState.UNASSESSED)
        self.assertEqual(by_title["CV à revoir"].preparation_state, PreparedRequirementState.REVIEW_REQUIRED)
        self.assertEqual(by_title["CV à revoir"].assessment_state, RequirementAssessmentState.UNASSESSED)
        self.assertEqual(result.readiness.status, ReadinessStatus.ACTION_REQUIRED)

    def test_no_policy_is_unknown_while_explicit_policy_with_no_candidate_is_missing(self):
        revision = self._draft_revision()
        no_policy = self._requirement(revision, title="Sans policy")
        missing = self._requirement(revision, title="Avec policy")
        self._policy(missing, key="missing")
        self._publish(revision)

        result = prepared_start_for_revision(actor=self.actor, revision=revision)
        by_title = {item.title: item for item in result.requirements}

        self.assertEqual(by_title[no_policy.title].preparation_state, PreparedRequirementState.UNKNOWN)
        self.assertEqual(by_title[missing.title].preparation_state, PreparedRequirementState.MISSING)
        self.assertEqual(result.summary.unknown_requirements, 1)
        self.assertEqual(result.summary.missing_requirements, 1)

    def test_expired_library_version_is_not_accepted(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision)
        self._policy(requirement, human_review=False)
        self._publish(revision)
        self._library_version(expires_at=timezone.localdate() - timedelta(days=1))

        result = prepared_start_for_revision(actor=self.actor, revision=revision)
        item = result.requirements[0]

        self.assertEqual(item.preparation_state, PreparedRequirementState.MISSING)
        self.assertIn(TrustedReuseReasonCode.EXPIRED.value, item.reason_codes)
        self.assertEqual(item.reuse_options, ())

    def test_exact_active_proof_can_be_reused_only_when_policy_accepts_exact_type(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision, title="Preuve de service")
        self._policy(
            requirement,
            source=RequirementReuseSource.PROOF,
            proof_type=ProofType.SERVICE_COMPLETED,
            require_not_expired=False,
            human_review=False,
        )
        self._publish(revision)
        proof = self._proof()

        result = prepared_start_for_revision(actor=self.actor, revision=revision)
        item = result.requirements[0]

        self.assertEqual(item.preparation_state, PreparedRequirementState.READY)
        self.assertEqual(item.reuse_options[0].candidate_source, RequirementReuseSource.PROOF)
        self.assertEqual(item.reuse_options[0].candidate_source_id, str(proof.pk))
        self.assertIn(TrustedReuseReasonCode.PROOF_TYPE_MATCH.value, item.reuse_options[0].reason_codes)

    def test_revoked_proof_never_makes_prepared_start_ready(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision, title="Preuve active")
        self._policy(
            requirement,
            source=RequirementReuseSource.PROOF,
            proof_type=ProofType.SERVICE_COMPLETED,
            require_not_expired=False,
            human_review=False,
        )
        self._publish(revision)
        self._proof(status=ProofStatus.REVOKED)

        result = prepared_start_for_revision(actor=self.actor, revision=revision)
        item = result.requirements[0]

        self.assertEqual(item.preparation_state, PreparedRequirementState.MISSING)
        self.assertIn(TrustedReuseReasonCode.PROOF_REVOKED.value, item.reason_codes)

    def test_revision_n_remains_exact_after_n_plus_one_and_revalidation_detects_newer(self):
        revision_n = self._draft_revision(title="Version N")
        requirement_n = self._requirement(revision_n, title="CV N")
        self._policy(requirement_n, human_review=False, key="n")
        self._publish(revision_n)
        self._library_version(expires_at=timezone.localdate() + timedelta(days=90))
        result_n = prepared_start_for_revision(actor=self.actor, revision=revision_n)

        revision_n1 = self._draft_revision(opportunity=revision_n.opportunity, title="Version N+1")
        requirement_n1 = self._requirement(revision_n1, title="CV N+1")
        self._policy(requirement_n1, human_review=False, key="n1")
        self._publish(revision_n1)

        self.assertEqual(result_n.revision_version, 1)
        self.assertEqual(result_n.requirements[0].title, "CV N")
        revalidation = revalidate_prepared_start_revision(result_n)
        self.assertTrue(revalidation.has_newer_revision)
        self.assertFalse(revalidation.is_current_revision)
        self.assertEqual(revalidation.current_revision_id, str(revision_n1.pk))
        self.assertEqual(revalidation.current_revision_version, 2)

    def test_dossier_authority_and_assignment_never_open_another_profiles_memory(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision)
        self._policy(requirement, human_review=False)
        self._publish(revision)
        self._library_version(subject=self.actor, expires_at=timezone.localdate() + timedelta(days=90))
        dossier = create_dossier(actor=self.other, owner_profile=self.other, title="Dossier privé")
        grant_dossier_authority(actor=self.other, dossier=dossier, profile=self.actor, role=SystemRoleCode.DOSSIER_MANAGER)
        assign_dossier(actor=self.other, dossier=dossier, assignee=self.actor)

        with self.assertRaises(PermissionDenied):
            prepared_start_for_revision(actor=self.actor, subject=self.other, revision=revision)

    def test_read_projection_has_no_business_side_effects(self):
        revision = self._draft_revision()
        requirement = self._requirement(revision)
        self._policy(requirement, human_review=False)
        self._publish(revision)
        self._library_version(expires_at=timezone.localdate() + timedelta(days=90))
        counters = {
            Journey: Journey.objects.count(),
            JourneyArtifact: JourneyArtifact.objects.count(),
            PersonalAssetUse: PersonalAssetUse.objects.count(),
            RequirementReuseApplication: RequirementReuseApplication.objects.count(),
            ServiceRequirementAssessment: ServiceRequirementAssessment.objects.count(),
            ServiceRequirementEvidence: ServiceRequirementEvidence.objects.count(),
            Proof: Proof.objects.count(),
            Payment: Payment.objects.count(),
            Access: Access.objects.count(),
        }

        prepared_start_for_revision(actor=self.actor, revision=revision)

        for model, before in counters.items():
            self.assertEqual(model.objects.count(), before, model.__name__)

    def test_query_growth_is_bounded_by_requirement_count(self):
        small = self._draft_revision(title="Small")
        small_requirement = self._requirement(small, title="Small CV")
        self._policy(small_requirement, human_review=False, key="small")
        self._publish(small)

        large = self._draft_revision(title="Large")
        for index in range(25):
            requirement = self._requirement(large, title=f"CV {index}", mandatory=index % 2 == 0)
            self._policy(requirement, human_review=False, key=f"policy-{index}")
        self._publish(large)
        self._library_version(expires_at=timezone.localdate() + timedelta(days=90))

        with CaptureQueriesContext(connection) as small_queries:
            prepared_start_for_revision(actor=self.actor, revision=small)
        with CaptureQueriesContext(connection) as large_queries:
            prepared_start_for_revision(actor=self.actor, revision=large)

        self.assertLessEqual(len(large_queries), len(small_queries) + 2)

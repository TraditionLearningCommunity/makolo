from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from requirements.models import RequirementReusePolicy, RequirementReuseSource
from requirements.trusted_reuse import TrustedReuseDecision, TrustedReuseDecisionCode, TrustedReuseReasonCode


class TrustedReusePolicyContractTests(TestCase):
    def setUp(self):
        Opportunity = apps.get_model("opportunities", "Opportunity")
        OpportunityRevision = apps.get_model("opportunities", "OpportunityRevision")
        OpportunityRequirement = apps.get_model("opportunities", "OpportunityRequirement")
        opportunity = Opportunity.objects.create(kind="job")
        self.revision = OpportunityRevision.objects.create(
            opportunity=opportunity,
            version=1,
            title="Programme test",
            issuer_name="Makolo test",
            timezone="UTC",
        )
        self.requirement = OpportunityRequirement.objects.create(
            revision=self.revision,
            kind="document",
            title="Pièce documentaire",
        )

    def test_document_policy_requires_exact_structured_kind(self):
        policy = RequirementReusePolicy.objects.create(
            requirement=self.requirement,
            key="cv-current",
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind="cv",
        )
        self.assertEqual(policy.artifact_kind, "cv")
        self.assertEqual(policy.proof_type, "")

        invalid = RequirementReusePolicy(
            requirement=self.requirement,
            key="invalid-document",
            source_type=RequirementReuseSource.LIBRARY,
            proof_type="service_completed",
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_proof_policy_requires_exact_proof_type(self):
        policy = RequirementReusePolicy.objects.create(
            requirement=self.requirement,
            key="service-proof",
            source_type=RequirementReuseSource.PROOF,
            proof_type="service_completed",
        )
        self.assertEqual(policy.proof_type, "service_completed")
        self.assertEqual(policy.artifact_kind, "")

    def test_policy_is_frozen_with_published_requirement_revision(self):
        policy = RequirementReusePolicy.objects.create(
            requirement=self.requirement,
            key="cv-current",
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind="cv",
        )
        self.revision.__class__.objects.filter(pk=self.revision.pk).update(published_at=timezone.now())
        policy.refresh_from_db()
        with self.assertRaises(ValidationError):
            policy.delete()

    def test_published_policy_cannot_be_bulk_deleted(self):
        policy = RequirementReusePolicy.objects.create(
            requirement=self.requirement,
            key="cv-bulk-delete-guard",
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind="cv",
        )
        self.revision.__class__.objects.filter(pk=self.revision.pk).update(published_at=timezone.now())
        # QuerySet.delete() owns an internal atomic block without a savepoint.
        # Isolate the expected signal exception so Django's TestCase transaction
        # remains usable for the assertion that the protected row still exists.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                RequirementReusePolicy.objects.filter(pk=policy.pk).delete()
        self.assertTrue(RequirementReusePolicy.objects.filter(pk=policy.pk).exists())

    def test_decision_contract_is_explainable_not_scored(self):
        decision = TrustedReuseDecision(
            requirement_id=str(self.requirement.pk),
            assessment_id="assessment-1",
            candidate_source="library",
            candidate_source_id="version-1",
            policy_id="policy-1",
            policy_key="cv-current",
            decision=TrustedReuseDecisionCode.ACCEPTABLE,
            reasons=(TrustedReuseReasonCode.LIBRARY_KIND_MATCH,),
            freshness="not_expired",
            sensitivity="normal",
            confirmation_required=False,
            materialization_path="personal_asset_version_to_journey_artifact",
            observed_at=timezone.now(),
        )
        self.assertTrue(decision.acceptable)
        self.assertFalse(hasattr(decision, "score"))
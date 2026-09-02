from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifactKind
from requirements.models import RequirementReusePolicy, RequirementReuseSource
from requirements.trusted_reuse import TrustedReuseDecisionCode, TrustedReuseReasonCode

from .test_q4_trusted_reuse import TrustedReuseQ4Tests
from .trusted_reuse import evaluate_trusted_reuse


class TrustedReuseAmbiguousPolicyQ4Tests(TestCase):
    setUp = TrustedReuseQ4Tests.setUp
    _add_requirement = TrustedReuseQ4Tests._add_requirement
    _assessment = TrustedReuseQ4Tests._assessment
    _asset_version = TrustedReuseQ4Tests._asset_version
    _candidate = TrustedReuseQ4Tests._candidate

    def test_multiple_exact_policies_return_unknown_instead_of_silent_selection(self):
        RequirementReusePolicy.objects.bulk_create([
            RequirementReusePolicy(
                requirement=self.doc_requirement,
                key="library-cv-duplicate",
                source_type=RequirementReuseSource.LIBRARY,
                artifact_kind=JourneyArtifactKind.CV,
                require_not_expired=True,
            )
        ])
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))

        decision = evaluate_trusted_reuse(
            assessment=self._assessment(self.doc_requirement),
            candidate=self._candidate(version.pk),
            actor=self.beneficiary,
        )

        self.assertEqual(decision.decision, TrustedReuseDecisionCode.UNKNOWN)
        self.assertIn(TrustedReuseReasonCode.POLICY_AMBIGUOUS, decision.reasons)

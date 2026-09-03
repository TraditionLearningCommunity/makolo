from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from personal_assets.action_memory import ActionMemorySource
from personal_assets.models import PersonalAssetUse
from requirements.models import RequirementReuseApplication

from .models import ServiceRequirementAssessment, ServiceRequirementEvidence
from .test_q4_trusted_reuse import TrustedReuseQ4Tests
from .trusted_reuse import apply_trusted_reuse

User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Q4 concurrency locking is validated on PostgreSQL only.")
class TrustedReuseConcurrencyPostgresTests(TransactionTestCase):
    setUp = TrustedReuseQ4Tests.setUp
    _add_requirement = TrustedReuseQ4Tests._add_requirement
    _assessment = TrustedReuseQ4Tests._assessment
    _asset_version = TrustedReuseQ4Tests._asset_version
    _candidate = TrustedReuseQ4Tests._candidate
    _active_proof = TrustedReuseQ4Tests._active_proof

    def test_two_simultaneous_applies_create_one_materialization_and_one_evidence(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        actor_id = self.beneficiary.pk
        assessment_id = assessment.pk
        version_id = version.pk
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            actor = User.objects.get(pk=actor_id)
            current_assessment = ServiceRequirementAssessment.objects.get(pk=assessment_id)
            barrier.wait(timeout=10)
            try:
                result = apply_trusted_reuse(
                    assessment=current_assessment,
                    actor=actor,
                    candidate_source=ActionMemorySource.LIBRARY,
                    candidate_source_id=version_id,
                )
                return (result.application_id, result.journey_artifact_id, result.evidence_id)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: worker(), range(2)))

        self.assertEqual(first, second)
        self.assertEqual(RequirementReuseApplication.objects.filter(assessment_id=assessment_id).count(), 1)
        self.assertEqual(ServiceRequirementEvidence.objects.filter(assessment_id=assessment_id).count(), 1)
        self.assertEqual(PersonalAssetUse.objects.filter(asset_version_id=version_id, journey_artifact__journey=self.journey).count(), 1)

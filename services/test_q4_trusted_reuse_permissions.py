from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey
from personal_assets.action_memory import ActionMemorySource

from .models import ServiceRequirementEvidence
from .test_q4_trusted_reuse import TrustedReuseQ4Tests
from .trusted_reuse import apply_trusted_reuse, evaluate_trusted_reuse

User = TrustedReuseQ4Tests.curator.field.model if hasattr(TrustedReuseQ4Tests, "curator") else None


class TrustedReusePermissionWithdrawalQ4Tests(TestCase):
    setUp = TrustedReuseQ4Tests.setUp
    _add_requirement = TrustedReuseQ4Tests._add_requirement
    _assessment = TrustedReuseQ4Tests._assessment
    _asset_version = TrustedReuseQ4Tests._asset_version
    _candidate = TrustedReuseQ4Tests._candidate

    def test_permission_removed_after_preview_blocks_apply_without_transmission(self):
        UserModel = self.beneficiary.__class__
        collaborator = UserModel.objects.create_user(
            username="q4-revoked-collaborator",
            email="q4-revoked-collaborator@example.test",
            password="x",
        )
        mandate = grant_activity_role(
            profile=collaborator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        assign_journey(
            journey=self.journey,
            profile=collaborator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )
        _, version = self._asset_version(
            controller=collaborator,
            subject=self.beneficiary,
            expires_at=timezone.localdate() + timezone.timedelta(days=30),
            text=b"permission-withdrawal",
        )
        assessment = self._assessment(self.doc_requirement)
        candidate = self._candidate(version.pk, actor=collaborator)
        preview = evaluate_trusted_reuse(
            assessment=assessment,
            candidate=candidate,
            actor=collaborator,
        )
        self.assertTrue(preview.acceptable)

        revoke_mandate(mandate=mandate, actor=self.manager)

        before_artifacts = self.journey.artifacts.count()
        before_evidence = ServiceRequirementEvidence.objects.filter(assessment=assessment).count()
        with self.assertRaises(PermissionDenied):
            apply_trusted_reuse(
                assessment=assessment,
                actor=collaborator,
                candidate_source=ActionMemorySource.LIBRARY,
                candidate_source_id=version.pk,
            )
        self.assertEqual(self.journey.artifacts.count(), before_artifacts)
        self.assertEqual(
            ServiceRequirementEvidence.objects.filter(assessment=assessment).count(),
            before_evidence,
        )

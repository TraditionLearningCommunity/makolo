from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifactSensitivity
from personal_assets.action_memory import ActionMemorySource

from .models import ServiceRequirementEvidence
from .test_q4_trusted_reuse import TrustedReuseQ4Tests


class TrustedReuseParticipantUiQ4Tests(TrustedReuseQ4Tests.__bases__[0]):
    setUp = TrustedReuseQ4Tests.setUp
    _add_requirement = TrustedReuseQ4Tests._add_requirement
    _assessment = TrustedReuseQ4Tests._assessment
    _asset_version = TrustedReuseQ4Tests._asset_version
    _candidate = TrustedReuseQ4Tests._candidate
    _active_proof = TrustedReuseQ4Tests._active_proof

    def _url(self, requirement=None):
        assessment = self._assessment(requirement or self.doc_requirement)
        return reverse("services:participant-trusted-reuse", args=[self.journey.pk, assessment.pk])

    def test_participant_sees_contextual_reuse_language_without_technical_policy_ids(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        self.client.force_login(self.beneficiary)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vous avez peut-être déjà ce qu’il faut")
        self.assertContains(response, "Utiliser ce document")
        self.assertContains(response, version.asset.title)
        self.assertNotContains(response, "TrustedReuseDecision")
        self.assertNotContains(response, "policy_id")

    def test_other_profile_cannot_open_participant_reuse_page(self):
        self.client.force_login(self.other)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 404)

    def test_sensitive_post_without_confirmation_transmits_nothing(self):
        _, version = self._asset_version(
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
            expires_at=timezone.localdate() + timedelta(days=30),
        )
        assessment = self._assessment(self.doc_requirement)
        self.client.force_login(self.beneficiary)
        response = self.client.post(
            self._url(),
            {"candidate_source": ActionMemorySource.LIBRARY.value, "candidate_source_id": str(version.pk)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.journey.artifacts.count(), 0)
        self.assertFalse(ServiceRequirementEvidence.objects.filter(assessment=assessment).exists())

    def test_confirmed_document_is_copied_and_submitted_without_auto_satisfaction(self):
        _, version = self._asset_version(expires_at=timezone.localdate() + timedelta(days=30))
        assessment = self._assessment(self.doc_requirement)
        self.client.force_login(self.beneficiary)
        response = self.client.post(
            self._url(),
            {"candidate_source": ActionMemorySource.LIBRARY.value, "candidate_source_id": str(version.pk)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceRequirementEvidence.objects.filter(assessment=assessment).exists())
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, "unassessed")

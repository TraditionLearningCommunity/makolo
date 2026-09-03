from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import create_artifact
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import create_journey
from trust.models import Proof, ProofStatus, ProofType

from .services import create_personal_asset, create_personal_asset_version


User = get_user_model()


def pdf_upload(text=b"q3-view"):
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n" + text + b"\n%%EOF",
        content_type="application/pdf",
    )


class ActionMemoryQ3ViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="q3-view-owner", email="q3-view-owner@example.test", password="x")
        self.operator = User.objects.create_user(username="q3-view-operator", email="q3-view-operator@example.test", password="x")
        self.activity = Activity.objects.create(
            owner_profile=self.operator,
            created_by=self.operator,
            title="Q3 view",
        )
        self.current = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        self.client.force_login(self.owner)

    def _asset_version(self, *, title, sensitivity=JourneyArtifactSensitivity.NORMAL, expires_at=None):
        asset = create_personal_asset(
            controller=self.owner,
            subject_profile=self.owner,
            title=title,
            kind=JourneyArtifactKind.CV,
            sensitivity=sensitivity,
        )
        version = create_personal_asset_version(
            actor=self.owner,
            asset=asset,
            uploaded_file=pdf_upload(title.encode("utf-8")),
            expires_at=expires_at,
        )
        return asset, version

    def test_action_memory_panel_explains_sources_and_only_offers_explicit_paths(self):
        _, sensitive_version = self._asset_version(
            title="CV sensible",
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )
        expired_asset, _ = self._asset_version(
            title="CV expiré",
            expires_at=timezone.localdate() - timedelta(days=1),
        )
        old = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        create_artifact(
            journey=old,
            uploaded_file=pdf_upload(b"certificate"),
            uploaded_by=self.owner,
            kind=JourneyArtifactKind.CERTIFICATE,
            title="Certificat ancien",
        )
        proof_journey = create_journey(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.FULFILLED,
        )
        Proof.objects.create(
            subject_profile=self.owner,
            journey=proof_journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            status=ProofStatus.ACTIVE,
        )

        response = self.client.get(reverse("personal_assets:use-in-journey", args=[self.current.pk]))

        self.assertContains(response, "Vous avez peut-être déjà ce qu’il faut")
        self.assertContains(response, "Rien n’est transmis automatiquement")
        self.assertContains(response, "CV sensible")
        self.assertContains(response, "confirmation requise")
        self.assertContains(response, f'value="{sensitive_version.pk}"')
        self.assertContains(response, "Confirmer et utiliser")
        self.assertContains(response, "Certificat ancien")
        self.assertContains(response, "Conserver dans Ma Bibliothèque")
        self.assertContains(response, "Consulter mes preuves")
        self.assertContains(response, "CV expiré")
        self.assertContains(response, "Vérifier dans Ma Bibliothèque")
        self.assertContains(response, reverse("personal_assets:detail", args=[expired_asset.pk]))
        self.assertNotContains(response, "score")

    def test_action_memory_use_action_still_delegates_to_q2_snapshot_service(self):
        _, version = self._asset_version(
            title="CV à utiliser",
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )

        response = self.client.post(
            reverse("personal_assets:use-in-journey", args=[self.current.pk]),
            {"version_id": str(version.pk)},
        )

        self.assertEqual(response.status_code, 302)
        artifact = self.current.artifacts.get()
        self.assertEqual(artifact.content_hash, version.content_hash)
        self.assertEqual(artifact.sensitivity, JourneyArtifactSensitivity.SENSITIVE)

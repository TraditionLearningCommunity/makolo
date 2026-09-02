import tempfile
from pathlib import Path

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Proof, ProofType, TrustEvidence, VerificationClaimType
from .services import attach_trust_evidence, issue_proof, request_verification
from .tests import TrustFixtureMixin


class TrustSecurityHardeningTests(TrustFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_trust_evidence_reuses_private_artifact_storage_without_public_url(self):
        field = TrustEvidence._meta.get_field("file")
        self.assertIsNone(field.storage.base_url)
        self.assertNotEqual(Path(field.storage.location), Path(tempfile.gettempdir()))
        with self.assertRaises(ValueError):
            field.storage.url("trust/private-evidence/example.pdf")

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_evidence_download_is_idor_protected(self):
        claim = request_verification(
            actor=self.owner,
            subject_space=self.space,
            claim_type=VerificationClaimType.ORGANIZATION_IDENTITY,
        )
        evidence = attach_trust_evidence(
            actor=self.owner,
            uploaded_file=SimpleUploadedFile(
                "proof.pdf", b"%PDF-1.4\nprivate", content_type="application/pdf"
            ),
            verification_claim=claim,
        )
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("trust:evidence-download", kwargs={"evidence_id": evidence.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_trust_admin_is_audit_only(self):
        request = type("Request", (), {"user": self.staff})()
        for model in (TrustEvidence, Proof):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
            self.assertEqual(
                set(model_admin.get_readonly_fields(request)),
                {field.name for field in model._meta.fields},
            )

    def test_staff_proof_revocation_requires_platform_authority_and_reason(self):
        proof = issue_proof(
            journey=self.fulfilled,
            proof_type=ProofType.JOURNEY_COMPLETED,
            actor=self.staff,
            is_public=True,
        )
        url = reverse("trust:staff-proof-revoke", kwargs={"proof_id": proof.pk})

        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {"reason": "invalid"}).status_code, 403)
        proof.refresh_from_db()
        self.assertEqual(proof.status, "active")

        self.client.force_login(self.staff)
        self.client.post(url, {"reason": ""})
        proof.refresh_from_db()
        self.assertEqual(proof.status, "active")

        response = self.client.post(url, {"reason": "source fact corrected"})
        self.assertEqual(response.status_code, 302)
        proof.refresh_from_db()
        self.assertEqual(proof.status, "revoked")
        self.assertEqual(proof.revoked_by_id, self.staff.pk)

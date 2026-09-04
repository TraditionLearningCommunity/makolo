from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from .credential_models import Credential, CredentialType
from .credential_services import issue_credential, revoke_credential
from .test_g5_credentials import CredentialFixtureMixin


class CredentialRevocationAuthorizationTests(CredentialFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.credential = issue_credential(
            activity=self.activity,
            subject_profile=self.participant,
            journey=self.journey,
            credential_type=CredentialType.COMPLETION,
            actor=self.owner,
        )
        revoke_credential(credential=self.credential, actor=self.owner, reason="withdrawn")

    def test_already_revoked_credential_still_requires_current_authority(self):
        with self.assertRaises(PermissionDenied):
            revoke_credential(
                credential=self.credential,
                actor=self.outsider,
                reason="unauthorized retry",
            )

    def test_queryset_delete_cannot_remove_credential_history(self):
        with self.assertRaises(ValidationError):
            Credential.objects.filter(pk=self.credential.pk).delete()
        self.assertTrue(Credential.objects.filter(pk=self.credential.pk).exists())

    def test_queryset_update_cannot_rewrite_credential_contract(self):
        original_title = self.credential.title
        with self.assertRaises(ValidationError):
            Credential.objects.filter(pk=self.credential.pk).update(title="silent rewrite")
        self.credential.refresh_from_db()
        self.assertEqual(self.credential.title, original_title)

    def test_bulk_update_cannot_rewrite_credential_contract(self):
        original_title = self.credential.title
        self.credential.title = "bulk rewrite"
        with self.assertRaises(ValidationError):
            Credential.objects.bulk_update([self.credential], ["title"])
        self.credential.refresh_from_db()
        self.assertEqual(self.credential.title, original_title)

    def test_public_verification_does_not_expose_internal_history_ids(self):
        url = reverse(
            "trust_api:credential-verify",
            kwargs={"public_id": self.credential.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("id", payload)
        self.assertNotIn("id", payload["beneficiary"])
        self.assertNotIn("id", payload["issuer"])
        self.assertNotIn("id", payload["source"]["activity"])
        self.assertNotIn("journey_id", payload["source"])
        self.assertNotIn("revoked_by_id", payload)
        self.assertNotIn("revoke_reason", payload)

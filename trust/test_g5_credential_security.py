from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

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

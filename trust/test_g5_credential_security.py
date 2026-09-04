from django.core.exceptions import PermissionDenied
from django.test import TestCase

from .credential_models import CredentialType
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

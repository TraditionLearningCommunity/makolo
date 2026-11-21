"""Stage 4: a verification token never bypasses current public source rights."""
from django.test import TestCase
from django.urls import reverse

from activities.models import ActivityVisibility
from sharing.passport import PASSPORT_PUBLIC, build_profile_passport
from sharing.passport_documents import (
    issue_passport_snapshot, passport_verification_token,
    profile_public_snapshot_still_disclosable,
)
from sharing.test_g6_passport import G6PassportFixtureMixin
from trust.credential_services import revoke_credential
from trust.models import ProofStatus


class PassportPublicWithdrawalTests(G6PassportFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def _issue_public(self):
        passport = build_profile_passport(self.amina, variant=PASSPORT_PUBLIC)
        return issue_passport_snapshot(passport)

    def _verify_anonymously(self, snapshot):
        return self.client.get(reverse(
            "sharing:passport-verify",
            kwargs={"token": passport_verification_token(snapshot)},
        ))

    def test_public_activity_becoming_private_hides_dated_public_document(self):
        issued = self._issue_public()
        self.assertTrue(profile_public_snapshot_still_disclosable(issued))
        self.owned_public.visibility = ActivityVisibility.PRIVATE
        self.owned_public.save(update_fields=["visibility"])
        self.assertFalse(profile_public_snapshot_still_disclosable(issued))
        response = self._verify_anonymously(issued)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_dated_passport"])
        self.assertNotContains(response, "Atelier Python G6")

    def test_proof_revocation_hides_old_public_proof_content(self):
        issued = self._issue_public()
        self.assertTrue(profile_public_snapshot_still_disclosable(issued))
        self.public_proof.status = ProofStatus.REVOKED
        self.public_proof.save(update_fields=["status"])
        self.assertFalse(profile_public_snapshot_still_disclosable(issued))
        response = self._verify_anonymously(issued)
        self.assertFalse(response.context["can_view_dated_passport"])

    def test_credential_revocation_hides_old_public_attestation_content(self):
        issued = self._issue_public()
        self.assertTrue(profile_public_snapshot_still_disclosable(issued))
        revoke_credential(
            credential=self.valid_credential, actor=self.space_owner,
            reason="Attestation retirée pour correction",
        )
        self.assertFalse(profile_public_snapshot_still_disclosable(issued))
        response = self._verify_anonymously(issued)
        self.assertFalse(response.context["can_view_dated_passport"])

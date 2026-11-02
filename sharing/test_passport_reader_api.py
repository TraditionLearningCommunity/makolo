"""Native Passport reader: same disclosure boundary as Web, no extra authority."""
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from sharing.passport import build_profile_passport
from sharing.passport_documents import (
    issue_passport_snapshot, passport_verification_token,
    revoke_passport_snapshot,
)
from sharing.passport_sharing import create_passport_share, revoke_passport_share


class PassportReaderAPIContracts(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="passport-reader-owner", bio="Description datée privée.",
        )
        self.visitor = User.objects.create_user(username="passport-reader-visitor")
        self.profile = UserProfile.objects.create(
            user=self.owner, public_profile=False, searchable=False,
        )
        UserProfile.objects.create(user=self.visitor)
        
    def _issue(self, variant):
        return issue_passport_snapshot(build_profile_passport(
            self.owner, variant=variant,
            selected_sections=("bio",) if variant == "custom" else None,
        ))

    def _verification_url(self, snapshot):
        return reverse("sharing_api:passport-verify-reader", kwargs={
            "token": passport_verification_token(snapshot),
        })

    def _share(self, snapshot):
        envelope, url = create_passport_share(
            snapshot=snapshot, actor=self.owner, days=7,
        )
        token = urlsplit(url).path.rstrip("/").split("/")[-1]
        return envelope, reverse(
            "sharing_api:passport-shared-reader", kwargs={"token": token},
        )

    def test_signed_verification_does_not_grant_private_document_to_stranger(self):
        issued = self._issue("complete")
        signed = self._verification_url(issued)
        anonymous = self.client.get(signed)
        self.assertEqual(anonymous.status_code, 200)
        data = anonymous.json()["data"]
        self.assertFalse(data["can_view_content"])
        self.assertIsNone(data["payload"])
        self.assertTrue(data["integrity_ok"])
        self.assertFalse(data["explicit_share"])
        self.assertNotIn("Description datée privée.", anonymous.content.decode())
        self.assertEqual(anonymous["Cache-Control"], "private, no-store")

        self.client.force_login(self.visitor)
        forbidden = self.client.get(signed)
        self.assertFalse(forbidden.json()["data"]["can_view_content"])
        self.client.force_login(self.owner)
        own = self.client.get(signed).json()["data"]
        self.assertTrue(own["can_view_content"])
        self.assertEqual(
            own["payload"]["identity"]["bio"], "Description datée privée.",
        )

    def test_public_verification_obeys_current_publication_not_searchability(self):
        self.profile.public_profile = True
        self.profile.searchable = False
        self.profile.save(update_fields=[
            "public_profile", "searchable", "updated_at",
        ])
        snapshot = self._issue("public")
        public = self.client.get(self._verification_url(snapshot))
        self.assertEqual(public.status_code, 200)
        self.assertTrue(public.json()["data"]["can_view_content"])
        self.assertEqual(
            public.json()["data"]["payload"]["variant"], "public",
        )

        self.profile.public_profile = False
        self.profile.save(update_fields=["public_profile", "updated_at"])
        hidden = self.client.get(self._verification_url(snapshot))
        self.assertFalse(hidden.json()["data"]["can_view_content"])
        self.assertIsNone(hidden.json()["data"]["payload"])

    def test_explicit_link_reads_only_issued_version_until_revoked(self):
        snapshot = self._issue("custom")
        envelope, url = self._share(snapshot)
        self.assertFalse(snapshot.public_at_issue)
        shared = self.client.get(url)
        self.assertEqual(shared.status_code, 200)
        data = shared.json()["data"]
        self.assertTrue(data["explicit_share"])
        self.assertTrue(data["can_view_content"])
        self.assertEqual(data["variant"], "custom")
        self.assertEqual(data["payload"]["identity"]["bio"], "Description datée privée.")
        self.assertIsNotNone(data["expires_at"])
        self.assertEqual(shared["Cache-Control"], "private, no-store")
        # Native and HTML must resolve the very same frozen, active document.
        link_token = url.rstrip("/").split("/")[-2]
        web = self.client.get(reverse(
            "sharing:passport-shared", kwargs={"token": link_token},
        ))
        self.assertEqual(web.status_code, 200)
        self.assertTrue(web.context["can_view_dated_passport"])
        self.assertEqual(web.context["dated_payload"], data["payload"])

        revoke_passport_share(envelope=envelope, actor=self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        # The independent signed verification still establishes issuance,
        # without giving the anonymous recipient a new viewing right.
        verified = self.client.get(self._verification_url(snapshot))
        self.assertFalse(verified.json()["data"]["can_view_content"])

    def test_expired_grant_is_unreadable_without_revoking_issuance(self):
        snapshot = self._issue("custom")
        envelope, url = self._share(snapshot)
        envelope.expires_at = timezone.now() - timedelta(seconds=1)
        envelope.save(update_fields=["expires_at", "updated_at"])
        self.assertEqual(self.client.get(url).status_code, 404)
        verified = self.client.get(self._verification_url(snapshot))
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["data"]["integrity_ok"])
        self.assertFalse(verified.json()["data"]["can_view_content"])

    def test_withdrawal_closes_share_and_retains_read_only_owner_archive(self):
        snapshot = self._issue("custom")
        _, url = self._share(snapshot)
        revoke_passport_snapshot(snapshot=snapshot, actor=self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        signed = self._verification_url(snapshot)
        public = self.client.get(signed).json()["data"]
        self.assertTrue(public["revoked"])
        self.assertFalse(public["can_view_content"])
        self.client.force_login(self.owner)
        owner = self.client.get(signed).json()["data"]
        self.assertTrue(owner["revoked"])
        self.assertTrue(owner["can_view_content"])
        self.assertEqual(owner["payload"]["identity"]["bio"], "Description datée privée.")

    def test_invalid_reader_references_fail_closed(self):
        for name in ("passport-verify-reader", "passport-shared-reader"):
            result = self.client.get(reverse(
                f"sharing_api:{name}", kwargs={"token": "not-a-valid-token"},
            ))
            self.assertEqual(result.status_code, 404)

"""Issuance history is immutable; publication and Sharing are independent."""
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from sharing.models import PassportSnapshot
from sharing.passport import build_profile_passport
from sharing.passport_documents import issue_passport_snapshot, passport_verification_token


User = get_user_model()


class PassportIssuanceAndSharingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="issued-passport-owner",
            password="Test-Issuance-2026-Strong!",
            bio="Présentation originale en mai.",
        )
        self.profile = UserProfile.objects.create(
            user=self.owner, public_profile=False, searchable=False,
        )
        self.visitor = User.objects.create_user(
            username="issued-passport-visitor",
            password="Test-Issuance-2026-Strong!",
        )
        UserProfile.objects.create(user=self.visitor)

    def _issue(self, variant="public"):
        return issue_passport_snapshot(
            build_profile_passport(self.owner, variant=variant),
        )

    def _verify_url(self, snapshot):
        return reverse(
            "sharing:passport-verify",
            kwargs={"token": passport_verification_token(snapshot)},
        )

    def test_ordinary_consultation_creates_no_historical_version(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("sharing:passport-me")).status_code, 200,
        )
        self.assertEqual(
            self.client.get(reverse("sharing:passport-me-history")).status_code,
            200,
        )
        self.assertFalse(PassportSnapshot.objects.exists())

    def test_past_private_issuance_does_not_become_public_later(self):
        private_issued = self._issue()
        self.assertFalse(private_issued.public_at_issue)
        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile", "updated_at"])
        anonymous = self.client.get(self._verify_url(private_issued))
        self.assertEqual(anonymous.status_code, 200)
        self.assertFalse(anonymous.context["can_view_dated_passport"])
        self.assertNotContains(anonymous, "Présentation originale en mai.")

        public_issued = self._issue()
        self.assertTrue(public_issued.public_at_issue)
        public_view = self.client.get(self._verify_url(public_issued))
        self.assertTrue(public_view.context["can_view_dated_passport"])
        self.assertContains(public_view, "Présentation originale en mai.")

        self.profile.public_profile = False
        self.profile.save(update_fields=["public_profile", "updated_at"])
        hidden = self.client.get(self._verify_url(public_issued))
        self.assertFalse(hidden.context["can_view_dated_passport"])
        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile", "updated_at"])
        visible_again = self.client.get(self._verify_url(public_issued))
        self.assertTrue(visible_again.context["can_view_dated_passport"])
        self.assertFalse(self.profile.searchable)

    def test_owner_reads_revoked_historical_version_but_visitor_cannot(self):
        snapshot = self._issue()
        self.profile.public_profile = True
        self.profile.save(update_fields=["public_profile", "updated_at"])
        snapshot.revoked_at = timezone.now()
        snapshot.save(update_fields=["revoked_at"])

        visitor = self.client.get(self._verify_url(snapshot))
        self.assertFalse(visitor.context["can_view_dated_passport"])
        self.client.force_login(self.owner)
        owner = self.client.get(self._verify_url(snapshot))
        self.assertTrue(owner.context["can_view_dated_passport"])
        self.assertContains(owner, "Présentation originale en mai.")
        self.assertContains(owner, "révoquée")

        version = self.client.get(
            f"/api/v1/me/passport/history/{snapshot.pk}/",
        )
        self.assertEqual(version.status_code, 200)
        self.assertTrue(version.json()["data"]["revoked"])

    def test_explicit_share_of_private_issued_version_is_not_publication(self):
        snapshot = self._issue(variant="custom")
        self.assertFalse(snapshot.public_at_issue)
        self.client.force_login(self.owner)
        issued_count = PassportSnapshot.objects.count()
        response = self.client.post(
            reverse(
                "sharing:passport-share-create",
                kwargs={"snapshot_id": snapshot.pk},
            ), {"days": "7"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PassportSnapshot.objects.count(), issued_count)
        self.assertTrue(response.context["share_url"])
        share_url = urlsplit(response.context["share_url"]).path

        self.client.logout()
        verified = self.client.get(self._verify_url(snapshot))
        self.assertFalse(verified.context["can_view_dated_passport"])
        shared = self.client.get(share_url)
        self.assertEqual(shared.status_code, 200)
        self.assertTrue(shared.context["is_explicit_share"])
        self.assertContains(shared, "Présentation originale en mai.")

        envelope = response.context["share_url"]
        from sharing.models import PassportShareSubject
        grant = PassportShareSubject.objects.get(snapshot=snapshot)
        self.client.force_login(self.owner)
        revoked = self.client.post(reverse(
            "sharing:passport-share-revoke",
            kwargs={"share_id": grant.envelope_id},
        ))
        self.assertEqual(revoked.status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(share_url).status_code, 404)

    def test_expired_share_is_unavailable_while_issuance_remains(self):
        snapshot = self._issue(variant="thematic")
        self.client.force_login(self.owner)
        response = self.client.post(reverse(
            "sharing:passport-share-create",
            kwargs={"snapshot_id": snapshot.pk},
        ), {"days": "1"})
        self.assertEqual(response.status_code, 200)
        url = urlsplit(response.context["share_url"]).path
        from sharing.models import PassportShareSubject
        grant = PassportShareSubject.objects.get(snapshot=snapshot)
        grant.envelope.expires_at = timezone.now() - timedelta(seconds=1)
        grant.envelope.save(update_fields=["expires_at", "updated_at"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(PassportSnapshot.objects.filter(pk=snapshot.pk).exists())

    def test_outsider_cannot_share_other_profile_and_complete_is_not_shareable(self):
        snapshot = self._issue(variant="custom")
        self.client.force_login(self.visitor)
        denied = self.client.post(reverse(
            "sharing:passport-share-create",
            kwargs={"snapshot_id": snapshot.pk},
        ), {"days": "7"})
        self.assertEqual(denied.status_code, 404)

        self.client.force_login(self.owner)
        complete = self._issue(variant="complete")
        rejected = self.client.post(reverse(
            "sharing:passport-share-create",
            kwargs={"snapshot_id": complete.pk},
        ), {"days": "7"})
        self.assertEqual(rejected.status_code, 400)

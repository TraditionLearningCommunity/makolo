"""Issuance history is immutable; publication and Sharing are independent."""
from datetime import timedelta
from urllib.parse import urlsplit
from unittest.mock import patch

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
            build_profile_passport(
                self.owner, variant=variant,
                selected_sections=("bio",) if variant == "custom" else None,
            ),
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

    def test_personal_issue_creates_dated_snapshot_without_download(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("personal-projections:passport-issue")
            + "?variant=custom&include=bio",
            data={}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(response.json()["meta"]["projection"],
                         "personal.me.passport.issuance")
        self.assertEqual(data["variant"], "custom")
        snapshot = PassportSnapshot.objects.get(pk=data["id"])
        self.assertEqual(snapshot.payload["identity"]["bio"], self.owner.bio)
        self.assertEqual(snapshot.variant, "custom")
        self.assertEqual(self.client.get(
            reverse("personal-projections:passport-history")
        ).json()["data"]["count"], 1)
        self.assertNotIn("application/pdf", response["Content-Type"])

    def test_personal_issue_is_auth_scoped_and_rejects_context_overrides(self):
        url = reverse("personal-projections:passport-issue")
        anonymous = self.client.post(url, data={}, content_type="application/json")
        self.assertIn(anonymous.status_code, (401, 403))
        self.client.force_login(self.owner)
        rejected = self.client.post(
            url + "?profile_id=" + str(self.visitor.pk),
            data={}, content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 400)
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

    def test_dated_public_personal_details_are_revoked_with_their_audience(self):
        from accounts.profile_visibility import replace_profile_visibility
        from sharing.passport_documents import profile_public_snapshot_still_disclosable

        self.owner.first_name = "Maya"
        self.owner.last_name = "Exemple"
        self.owner.phone = "+243811000000"
        self.owner.save(update_fields=["first_name", "last_name", "phone", "updated_at"])
        self.profile.country = "CD"
        self.profile.city = "Lubumbashi"
        self.profile.public_profile = True
        self.profile.save(
            update_fields=["country", "city", "public_profile", "updated_at"],
        )
        snapshot = self._issue("public")
        personal = snapshot.payload["identity"]["presentation_details"]
        self.assertEqual(personal["first_name"], "Maya")
        self.assertEqual(personal["country"], "CD")
        self.assertNotIn("phone", personal)
        self.assertTrue(profile_public_snapshot_still_disclosable(snapshot))

        replace_profile_visibility(
            owner=self.owner, target_kind="field",
            field_key="city", audiences=[],
        )
        self.assertFalse(profile_public_snapshot_still_disclosable(snapshot))
        browser = self.client.get(self._verify_url(snapshot))
        self.assertEqual(browser.status_code, 200)
        self.assertFalse(browser.context["can_view_dated_passport"])

    def test_historical_pdf_download_never_issues_again_or_changes_owner(self):
        from io import BytesIO
        from pypdf import PdfReader

        snapshot = self._issue("complete")
        original_hash = snapshot.payload_hash
        self.client.force_login(self.owner)
        url = reverse(
            "personal-projections:passport-version-pdf",
            kwargs={"snapshot_id": snapshot.pk},
        )
        before = PassportSnapshot.objects.count()
        pdf = self.client.get(url)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertEqual(PassportSnapshot.objects.count(), before)
        self.assertIn(
            snapshot.document_id,
            "\\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages),
        )
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.payload_hash, original_hash)

        self.client.force_login(self.visitor)
        self.assertEqual(self.client.get(url).status_code, 404)

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

    def test_owner_withdraws_issued_document_and_all_its_active_links(self):
        from sharing.models import PassportShareSubject, ShareStatus

        snapshot = self._issue(variant="custom")
        self.client.force_login(self.owner)
        created = self.client.post(reverse(
            "sharing:passport-share-create",
            kwargs={"snapshot_id": snapshot.pk},
        ), {"days": "7"})
        self.assertEqual(created.status_code, 200)
        link = urlsplit(created.context["share_url"]).path
        grant = PassportShareSubject.objects.get(snapshot=snapshot)
        self.assertEqual(self.client.get(link).status_code, 200)

        withdrawn = self.client.post(reverse(
            "sharing:passport-version-revoke",
            kwargs={"snapshot_id": snapshot.pk},
        ))
        self.assertEqual(withdrawn.status_code, 302)
        snapshot.refresh_from_db()
        grant.envelope.refresh_from_db()
        self.assertTrue(snapshot.is_revoked)
        self.assertEqual(grant.envelope.status, ShareStatus.REVOKED)
        self.assertEqual(self.client.get(link).status_code, 404)

        # Revocation is idempotent and never deletes or changes the archive.
        before = snapshot.payload_hash
        again = self.client.post(reverse(
            "sharing:passport-version-revoke",
            kwargs={"snapshot_id": snapshot.pk},
        ))
        self.assertEqual(again.status_code, 302)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.payload_hash, before)
        version = self.client.get(f"/api/v1/me/passport/history/{snapshot.pk}/")
        self.assertEqual(version.status_code, 200)
        self.assertTrue(version.json()["data"]["revoked"])

    def test_native_share_listing_and_individual_revocation(self):
        from sharing.models import PassportShareSubject, ShareStatus

        snapshot = self._issue(variant="custom")
        self.client.force_login(self.owner)
        created = self.client.post(
            f"/api/v1/me/passport/history/{snapshot.pk}/share/",
            data='{"days": 30}',
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200)
        share_id = created.json()["data"]["share_id"]
        grant = PassportShareSubject.objects.get(snapshot=snapshot)
        self.assertEqual(str(grant.envelope_id), share_id)
        listed = self.client.get("/api/v1/me/passport/history/")
        item = listed.json()["data"]["items"][0]
        self.assertEqual(item["active_shares"][0]["id"], share_id)
        self.assertIsNotNone(item["active_shares"][0]["expires_at"])

        revoked = self.client.post(
            f"/api/v1/me/passport/shares/{share_id}/revoke/",
            data="{}", content_type="application/json",
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertTrue(revoked.json()["data"]["revoked"])
        grant.envelope.refresh_from_db()
        self.assertEqual(grant.envelope.status, ShareStatus.REVOKED)
        snapshot.refresh_from_db()
        self.assertFalse(snapshot.is_revoked)
        self.assertEqual(
            self.client.get("/api/v1/me/passport/history/").json()
            ["data"]["items"][0]["active_shares"], [],
        )

    def test_failed_pdf_render_never_emits_a_phantom_version(self):
        self.client.force_login(self.owner)
        count_before = PassportSnapshot.objects.count()
        with patch(
            "sharing.passport_pdf.render_passport_layout",
            side_effect=RuntimeError("PDF renderer unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.get(reverse("sharing:passport-me"), {
                    "pdf": "1", "variant": "complete",
                })
        self.assertEqual(PassportSnapshot.objects.count(), count_before)

    def test_failed_html_export_does_not_leave_an_issued_version(self):
        self.client.force_login(self.owner)
        before = PassportSnapshot.objects.count()
        with patch(
            "sharing.passport_views.PassportViewMixin.render_to_response",
            side_effect=RuntimeError("HTML template unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.get(reverse("sharing:passport-me"), {
                    "download": "1", "variant": "complete",
                })
        self.assertEqual(PassportSnapshot.objects.count(), before)

    def test_another_profile_cannot_revoke_document_or_link(self):
        from sharing.models import PassportShareSubject

        snapshot = self._issue(variant="custom")
        self.client.force_login(self.owner)
        self.client.post(reverse(
            "sharing:passport-share-create",
            kwargs={"snapshot_id": snapshot.pk},
        ), {"days": "7"})
        grant = PassportShareSubject.objects.get(snapshot=snapshot)
        self.client.force_login(self.visitor)
        self.assertEqual(self.client.post(reverse(
            "sharing:passport-version-revoke",
            kwargs={"snapshot_id": snapshot.pk},
        )).status_code, 404)
        self.assertEqual(self.client.post(
            f"/api/v1/me/passport/history/{snapshot.pk}/revoke/",
            data="{}", content_type="application/json",
        ).status_code, 404)
        self.assertEqual(self.client.post(
            f"/api/v1/me/passport/shares/{grant.envelope_id}/revoke/",
            data="{}", content_type="application/json",
        ).status_code, 404)
        snapshot.refresh_from_db()
        grant.envelope.refresh_from_db()
        self.assertFalse(snapshot.is_revoked)
        self.assertTrue(grant.envelope.is_active_at())

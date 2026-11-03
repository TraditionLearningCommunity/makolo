"""Regression coverage for the collective Passport, reusing G6 domain facts."""
from django.test import TestCase
from django.urls import reverse

from organizations.models import Team, TeamMembership, TeamMembershipStatus
from sharing.models import PassportSnapshot
from sharing.passport import build_space_passport
from sharing.test_g6_passport import G6PassportFixtureMixin


class SpacePassportNativeContractTests(G6PassportFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.client.force_login(self.space_owner)
        self.root = reverse(
            "organizations_api:workspace-passport",
            kwargs={"slug": self.space.slug},
        )
        self.base = "/api/v1/organizations/workspaces/" + self.space.slug + "/passport/"

    def test_complete_source_public_allowlist_and_no_private_public_fact(self):
        response = self.client.get(self.root)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["slug"], self.space.slug)
        self.assertEqual(data["variant"], "complete")
        self.assertTrue(data["public_profile_enabled"])
        all_ids = {row["id"] for row in data["activities"]}
        admitted = set(data["composition"]["public_ids"]["activities"])
        self.assertIn(str(self.space_public_activity.pk), all_ids)
        self.assertIn(str(self.space_private_activity.pk), all_ids)
        self.assertEqual(admitted, {str(self.space_public_activity.pk)})
        self.assertEqual(
            data["identity"]["owner_details"]["email"],
            self.space.contact_email,
        )
        self.assertEqual(
            data["identity"]["owner_details"]["phone"],
            self.space.contact_phone,
        )
        self.assertNotIn(
            self.space.contact_email,
            str(data["composition"]["public_identity"]),
        )
        self.assertNotIn(
            self.space.contact_phone,
            str(data["composition"]["public_identity"]),
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_thematic_and_personalized_never_reinclude_private_activity(self):
        for variant in ("public", "thematic", "custom"):
            projection = build_space_passport(
                self.space, variant=variant,
                topic_codes=["g6-health"] if variant == "thematic" else (),
            )
            ids = {str(row.pk) for row in projection.activities}
            self.assertNotIn(str(self.space_private_activity.pk), ids)
            if variant == "custom":
                self.assertIn(str(self.space_public_activity.pk), ids)

        # A forbidden ID is always rejected; it cannot be used to infer
        # private Activities or bypass public admission.
        bad = self.client.post(
            self.base + "issue/?variant=custom&exclude_activity=" +
            str(self.space_private_activity.pk),
        )
        self.assertEqual(bad.status_code, 400)

        good = self.client.post(
            self.base + "issue/?variant=custom&exclude_activity=" +
            str(self.space_public_activity.pk),
        )
        self.assertEqual(good.status_code, 200)
        snapshot = PassportSnapshot.objects.get(pk=good.json()["data"]["id"])
        self.assertEqual(snapshot.payload["activities"], [])

    def test_owner_issues_pdf_history_share_revoke_and_dated_download(self):
        issued = self.client.post(self.base + "issue/?variant=public")
        self.assertEqual(issued.status_code, 200)
        snapshot_id = issued.json()["data"]["id"]
        self.assertEqual(PassportSnapshot.objects.filter(space=self.space).count(), 1)
        version = self.client.get(self.base + "history/" + snapshot_id + "/")
        self.assertEqual(version.status_code, 200)
        self.assertEqual(version.json()["data"]["payload"]["variant"], "public")
        dated_pdf = self.client.get(
            self.base + "history/" + snapshot_id + "/pdf/",
        )
        self.assertEqual(dated_pdf.status_code, 200)
        self.assertTrue(dated_pdf.content.startswith(b"%PDF-"))
        self.assertEqual(PassportSnapshot.objects.filter(space=self.space).count(), 1)

        share = self.client.post(
            self.base + "history/" + snapshot_id + "/share/",
            {"days": 7},
        )
        self.assertEqual(share.status_code, 200)
        self.assertIn("/passport/shared/", share.json()["data"]["share_url"])
        history = self.client.get(self.base + "history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["data"]["count"], 1)
        self.assertEqual(len(history.json()["data"]["items"][0]["active_shares"]), 1)
        revoked = self.client.post(
            self.base + "history/" + snapshot_id + "/revoke/",
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertTrue(revoked.json()["data"]["revoked"])
        after = self.client.get(self.base + "history/")
        self.assertEqual(after.json()["data"]["items"][0]["active_shares"], [])

    def test_pdf_action_creates_exactly_one_dated_version(self):
        before = PassportSnapshot.objects.filter(space=self.space).count()
        pdf = self.client.get(self.base + "pdf/?variant=public")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(PassportSnapshot.objects.filter(space=self.space).count(), before + 1)

    def test_member_without_space_mandate_cannot_read_or_mutate(self):
        team = Team.objects.create(
            organization=self.space, name="Membres sans mandat",
        )
        TeamMembership.objects.create(
            team=team, user=self.outsider,
            status=TeamMembershipStatus.ACTIVE,
        )
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.root).status_code, 404)
        self.assertEqual(
            self.client.post(self.base + "issue/?variant=public").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.base + "history/").status_code, 404,
        )
        self.assertEqual(self.client.get(self.base + "pdf/").status_code, 404)

    def test_public_issued_document_does_not_include_collective_contacts(self):
        self.client.post(self.base + "issue/?variant=public")
        snapshot = PassportSnapshot.objects.filter(
            space=self.space, variant="public",
        ).latest("generated_at")
        self.assertEqual(snapshot.payload["identity"]["owner_details"], {})
        self.assertNotIn(self.space.contact_email, str(snapshot.payload))
        self.assertNotIn(self.space.contact_phone, str(snapshot.payload))

    def test_complete_issued_version_is_not_shareable_by_link(self):
        issued = self.client.post(self.base + "issue/?variant=complete")
        self.assertEqual(issued.status_code, 200)
        id = issued.json()["data"]["id"]
        denied = self.client.post(
            self.base + "history/" + id + "/share/", {"days": 7},
        )
        self.assertEqual(denied.status_code, 400)

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
)


class PersonalResourceApiTests(APITestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="resource-api-owner",
            email="resource-api-owner@example.test",
        )
        self.other = User.objects.create_user(
            username="resource-api-other",
            email="resource-api-other@example.test",
        )
        self.client.force_authenticate(self.profile)

    def _pdf(self, name="document.pdf", marker=b"one"):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4\n% Makolo " + marker + b"\n%%EOF\n",
            content_type="application/pdf",
        )

    def _create(self, title="Passeport RDC"):
        response = self.client.post(
            reverse("personal-projections:resource-create"),
            {
                "title": title,
                "kind": JourneyArtifactKind.IDENTITY_DOCUMENT,
                "sensitivity": JourneyArtifactSensitivity.NORMAL,
                "file": self._pdf(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response

    def test_create_returns_owner_detail_and_mutation_links(self):
        response = self._create()
        data = response.data["data"]
        self.assertEqual(data["title"], "Passeport RDC")
        self.assertEqual(data["current_version"]["version"], 1)
        self.assertIn("add_version", data["links"])
        self.assertIn("archive", data["links"])
        self.assertIn("download", data["links"])
        self.assertIn("reuse_in_journey", data["links"])

    def test_add_version_preserves_version_history(self):
        created = self._create()
        asset_id = created.data["data"]["id"]
        response = self.client.post(
            reverse(
                "personal-projections:resource-version-create",
                kwargs={"pk": asset_id},
            ),
            {"file": self._pdf(marker=b"two")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data["data"]
        self.assertEqual(data["current_version"]["version"], 2)
        self.assertEqual(data["versions"]["page"]["count"], 2)

    def test_archive_moves_document_out_of_current_view(self):
        created = self._create()
        asset_id = created.data["data"]["id"]
        response = self.client.post(
            reverse(
                "personal-projections:resource-archive",
                kwargs={"pk": asset_id},
            ),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["status"], "archived")
        self.assertNotIn("download", response.data["data"]["links"])

        current = self.client.get(
            reverse("personal-projections:resources"),
            {"view": "current"},
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data["data"]["documents"]["count"], 0)

        archived = self.client.get(
            reverse("personal-projections:resources"),
            {"view": "archived"},
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.data["data"]["documents"]["count"], 1)
        self.assertEqual(
            archived.data["data"]["documents"]["items"][0]["status"],
            "archived",
        )

    def test_collection_applies_owner_filters_and_sort_contract(self):
        self._create("Z identité")
        response = self.client.get(
            reverse("personal-projections:resources"),
            {
                "kind": JourneyArtifactKind.IDENTITY_DOCUMENT,
                "sensitivity": JourneyArtifactSensitivity.NORMAL,
                "sort": "title",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        documents = response.data["data"]["documents"]
        self.assertEqual(documents["filters"]["kind"], "identity_document")
        self.assertEqual(documents["filters"]["sensitivity"], "normal")
        self.assertEqual(documents["sort"], "title")
        self.assertIn("create", documents["links"])
        self.assertEqual(documents["items"][0]["title"], "Z identité")

    def test_other_profile_cannot_read_or_mutate_document(self):
        created = self._create()
        asset_id = created.data["data"]["id"]
        self.client.force_authenticate(self.other)

        detail = self.client.get(
            reverse(
                "personal-projections:resource-detail",
                kwargs={"pk": asset_id},
            )
        )
        self.assertEqual(detail.status_code, 404)

        version = self.client.post(
            reverse(
                "personal-projections:resource-version-create",
                kwargs={"pk": asset_id},
            ),
            {"file": self._pdf(marker=b"other")},
            format="multipart",
        )
        self.assertEqual(version.status_code, 404)

        archive = self.client.post(
            reverse(
                "personal-projections:resource-archive",
                kwargs={"pk": asset_id},
            ),
            {},
            format="json",
        )
        self.assertEqual(archive.status_code, 404)

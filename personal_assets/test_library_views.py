
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from personal_assets.services import (
    archive_personal_asset,
    create_personal_asset,
    create_personal_asset_version,
)


class PersonalLibraryMatureWebTests(TestCase):
    def setUp(self):
        self.profile = User.objects.create_user(
            username="library-owner",
            email="library-owner@example.test",
        )
        self.client.force_login(self.profile)

    def _asset(self, title):
        asset = create_personal_asset(
            controller=self.profile,
            subject_profile=self.profile,
            title=title,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            sensitivity=JourneyArtifactSensitivity.NORMAL,
        )
        create_personal_asset_version(
            actor=self.profile,
            asset=asset,
            uploaded_file=SimpleUploadedFile(
                "document.pdf",
                b"Makolo test document",
                content_type="application/pdf",
            ),
        )
        return asset

    def test_library_search_is_title_scoped_and_paginated(self):
        self._asset("Passeport RDC")
        self._asset("Diplôme Licence")
        response = self.client.get(
            reverse("personal_assets:list"),
            {"q": "Passeport"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passeport RDC")
        self.assertNotContains(response, "Diplôme Licence")
        self.assertContains(response, "Rechercher dans mes documents")
        self.assertEqual(response.context["page"].paginator.per_page, 24)

    def test_unknown_provenance_stays_unknown(self):
        asset = self._asset("Document sans provenance")
        response = self.client.get(
            reverse("personal_assets:detail", kwargs={"asset_id": asset.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Provenance inconnue")
        self.assertNotContains(response, "Ajouté à Ma Bibliothèque")

    def test_archived_asset_remains_readable_without_download_action(self):
        asset = self._asset("Document archivé")
        archive_personal_asset(actor=self.profile, asset=asset)
        response = self.client.get(
            reverse("personal_assets:detail", kwargs={"asset_id": asset.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Archivé")
        self.assertContains(response, "retirée de vos ressources courantes")
        self.assertNotContains(response, ">Télécharger<")

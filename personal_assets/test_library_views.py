from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
)
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

    def _asset(
        self,
        title,
        *,
        kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
        sensitivity=JourneyArtifactSensitivity.NORMAL,
        expires_at=None,
    ):
        asset = create_personal_asset(
            controller=self.profile,
            subject_profile=self.profile,
            title=title,
            kind=kind,
            sensitivity=sensitivity,
        )
        create_personal_asset_version(
            actor=self.profile,
            asset=asset,
            uploaded_file=SimpleUploadedFile(
                "document.pdf",
                b"%PDF-1.4\n% Makolo test document\n%%EOF\n",
                content_type="application/pdf",
            ),
            expires_at=expires_at,
        )
        return asset

    def test_resources_hub_keeps_three_families_distinct(self):
        self._asset("Passeport RDC")
        response = self.client.get(reverse("personal_assets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, "Mes documents")
        self.assertContains(response, "Mes preuves")
        self.assertContains(response, "Mes titres")
        self.assertContains(response, "Fichiers et pièces personnelles")
        self.assertNotContains(response, "Bibliothèque")

    def test_documents_search_is_title_scoped_and_paginated(self):
        self._asset("Passeport RDC")
        self._asset("Diplôme Licence")
        response = self.client.get(
            reverse("personal_assets:documents"),
            {"q": "Passeport"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passeport RDC")
        self.assertNotContains(response, "Diplôme Licence")
        self.assertContains(response, 'placeholder="Rechercher"')
        self.assertEqual(response.context["page"].paginator.per_page, 24)

    def test_documents_filter_sort_and_expiring_view(self):
        soon = timezone.localdate() + timedelta(days=10)
        self._asset(
            "Z identité",
            expires_at=soon,
            sensitivity=JourneyArtifactSensitivity.SENSITIVE,
        )
        self._asset(
            "A formulaire",
            kind=JourneyArtifactKind.FORM,
        )

        response = self.client.get(
            reverse("personal_assets:documents"),
            {
                "view": "expiring",
                "sensitivity": JourneyArtifactSensitivity.SENSITIVE,
                "sort": "title",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Z identité")
        self.assertNotContains(response, "A formulaire")

        response = self.client.get(
            reverse("personal_assets:documents"),
            {"sort": "title"},
        )
        titles = [item["asset"].title for item in response.context["items"]]
        self.assertEqual(titles, sorted(titles))

    def test_document_detail_preserves_only_its_safe_collection_return(self):
        asset = self._asset("Document contextuel")
        detail = reverse(
            "personal_assets:detail",
            kwargs={"asset_id": asset.pk},
        )
        expected = reverse("personal_assets:documents") + "?q=Document&sort=title"

        response = self.client.get(detail, {"return": expected})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["return_url"], expected)

        rejected = self.client.get(
            detail,
            {"return": "https://evil.example/library/documents/?q=secret"},
        )
        self.assertEqual(
            rejected.context["return_url"],
            reverse("personal_assets:documents"),
        )

    def test_unknown_provenance_stays_unknown(self):
        asset = self._asset("Document sans provenance")
        response = self.client.get(
            reverse("personal_assets:detail", kwargs={"asset_id": asset.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertContains(response, "Provenance")
        self.assertContains(response, "Inconnue")
        self.assertNotContains(response, "Ajouté à Ma Bibliothèque")

    def test_archived_asset_remains_readable_without_download_action(self):
        asset = self._asset("Document archivé")
        archive_personal_asset(actor=self.profile, asset=asset)
        response = self.client.get(
            reverse("personal_assets:detail", kwargs={"asset_id": asset.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Archivé")
        self.assertNotContains(response, 'aria-label="Télécharger"')

        archived = self.client.get(
            reverse("personal_assets:documents"),
            {"view": "archived"},
        )
        self.assertContains(archived, "Document archivé")

from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from rest_framework.test import APIClient

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role, revoke_mandate
from organizations.models import Organization
from sharing.space_document_sharing import (
    share_space_document, space_document_delivery,
    revoke_space_document_share,
)
from sharing.services import ShareUnavailable

from .models import SpaceDocument, SpaceDocumentVersion
from .services import (
    add_document_version, archive_document, can_manage_documents,
    create_document, use_document_in_journey, version_for_download,
)


def pdf(label="Document"):
    return SimpleUploadedFile(
        "statuts.pdf", (b"%PDF-1.4\n" + label.encode("utf-8") + b"\n%%EOF"),
        content_type="application/pdf",
    )


class SpaceDocumentTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="space-doc-owner", email="owner@test.local", password="x",
        )
        self.other = User.objects.create_user(
            username="space-doc-outside", email="outside@test.local", password="x",
        )
        self.recipient = User.objects.create_user(
            username="space-doc-recipient", email="recipient@test.local", password="x",
        )
        self.other_owner = User.objects.create_user(
            username="space-doc-second-owner", email="coowner@test.local", password="x",
        )
        for user in (self.owner, self.other, self.recipient, self.other_owner):
            UserProfile.objects.get_or_create(user=user)
        self.space = Organization.objects.create(
            name="Institution", slug="space-doc-institution",
            created_by=self.owner,
        )
        self.other_space = Organization.objects.create(
            name="Autre institution", slug="space-doc-other",
            created_by=self.other,
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        grant_space_role(
            profile=self.other_owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.base = (
            f"/api/v1/organizations/workspaces/{self.space.slug}/documents/"
        )

    def create(self, *, visibility="restricted"):
        return create_document(
            actor=self.owner, space=self.space, title="Statuts collectifs",
            uploaded_file=pdf(), visibility=visibility,
        )

    def test_institutional_ownership_and_immutable_versions(self):
        doc, first = self.create()
        self.assertEqual(doc.space_id, self.space.id)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.mime_type, "application/pdf")
        self.assertNotIn("personal_assets/", first.file.name)
        with self.assertRaises(ValueError):
            first.file.url
        second = add_document_version(
            actor=self.owner, document=doc, uploaded_file=pdf("Version 2"),
        )
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertNotEqual(second.content_hash, first.content_hash)
        first.file.open("rb")
        self.assertIn(b"Document", first.file.read())
        with self.assertRaises(ValidationError):
            first.save()
        with self.assertRaises(ValidationError):
            first.delete()
        with self.assertRaises(ValidationError):
            doc.delete()

    def test_role_revocation_removes_all_document_authority(self):
        doc, version = self.create()
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.base).status_code, 200)
        self.assertEqual(self.client.get(
            f"{self.base}versions/{version.pk}/download/"
        ).status_code, 200)
        revoke_mandate(mandate=self.owner_mandate, actor=self.other_owner)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(
            f"{self.base}{doc.pk}/"
        ).status_code, 404)
        self.assertEqual(self.client.get(
            f"{self.base}versions/{version.pk}/download/"
        ).status_code, 404)

    def test_no_member_or_other_space_has_implicit_authority(self):
        doc, version = self.create()
        self.assertFalse(can_manage_documents(self.other, self.space))
        with self.assertRaises(PermissionDenied):
            version_for_download(
                actor=self.other, space=self.space,
                version_id=version.pk,
            )
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(
            self.client.get(
                f"{self.base}versions/{version.pk}/download/"
            ).status_code, 404,
        )
        self.client.force_authenticate(self.recipient)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(
            f"{self.base}{doc.pk}/"
        ).status_code, 404)

    def test_authorized_upload_update_download_and_archive(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.base,
            {"title": "Statuts", "visibility": "restricted", "file": pdf()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        document_id = response.data["document"]["id"]
        version_id = response.data["version_id"]
        collection = self.client.get(self.base)
        self.assertEqual(collection.status_code, 200, collection.data)
        self.assertEqual(collection.data["count"], 1)
        detail = self.client.get(f"{self.base}{document_id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["document"]["latest_version"], 1)
        self.assertNotIn("file", str(detail.data))
        self.assertNotIn("content_hash", str(detail.data))
        download = self.client.get(
            f"{self.base}versions/{version_id}/download/"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Cache-Control"], "private, no-store")
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        added = self.client.post(
            f"{self.base}{document_id}/versions/",
            {"file": pdf("Deuxième")}, format="multipart",
        )
        self.assertEqual(added.status_code, 201, added.data)
        self.assertEqual(added.data["number"], 2)
        self.assertEqual(
            SpaceDocumentVersion.objects.filter(document_id=document_id).count(), 2,
        )
        archived = self.client.delete(f"{self.base}{document_id}/")
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(
            self.client.get(f"{self.base}{document_id}/").status_code, 404,
        )
        self.assertEqual(
            self.client.get(
                f"{self.base}versions/{version_id}/download/"
            ).status_code, 404,
        )

    def test_cannot_upload_disguised_or_empty_file(self):
        self.client.force_authenticate(self.owner)
        for payload in (
            SimpleUploadedFile(
                "statuts.pdf", b"not-a-pdf",
                content_type="application/pdf",
            ),
            SimpleUploadedFile(
                "statuts.pdf", b"",
                content_type="application/pdf",
            ),
        ):
            response = self.client.post(
                self.base,
                {"title": "Trompeur", "file": payload},
                format="multipart",
            )
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(SpaceDocument.objects.exists())

    def test_cross_space_and_terminal_journey_reuse_are_refused(self):
        _, version = self.create()
        foreign_journey = SimpleNamespace(
            status="draft",
            activity=SimpleNamespace(space_id=self.other_space.pk),
        )
        with self.assertRaises(PermissionDenied):
            use_document_in_journey(
                actor=self.owner,
                document_version=version,
                journey=foreign_journey,
            )
        completed = SimpleNamespace(
            status="fulfilled",
            activity=SimpleNamespace(space_id=self.space.pk),
        )
        with self.assertRaises(ValidationError):
            use_document_in_journey(
                actor=self.owner,
                document_version=version,
                journey=completed,
            )

    def test_explicit_recipient_share_expiry_and_revoke(self):
        doc, version = self.create()
        delivery = share_space_document(
            actor=self.owner, version=version,
            recipient=self.recipient.profile, days=1,
        )
        resolved, issued = space_document_delivery(
            user=self.recipient, delivery_id=delivery.pk,
        )
        self.assertEqual(issued.pk, version.pk)
        self.assertEqual(resolved.pk, delivery.pk)
        with self.assertRaises(PermissionDenied):
            space_document_delivery(
                user=self.other, delivery_id=delivery.pk,
            )
        response_url = (
            "/api/v1/sharing/documents/deliveries/"
            f"{delivery.pk}/download/"
        )
        self.client.force_authenticate(self.other)
        self.assertIn(self.client.get(response_url).status_code, (403, 404))
        self.client.force_authenticate(self.recipient)
        self.assertEqual(self.client.get(response_url).status_code, 200)
        revoke_space_document_share(
            actor=self.other_owner, delivery_id=delivery.pk,
        )
        with self.assertRaises(ShareUnavailable):
            space_document_delivery(
                user=self.recipient, delivery_id=delivery.pk,
            )
        next_delivery = share_space_document(
            actor=self.owner, version=version,
            recipient=self.recipient.profile, days=1,
        )
        next_delivery.envelope.expires_at = timezone.now() - timedelta(seconds=1)
        next_delivery.envelope.save(update_fields=["expires_at"])
        with self.assertRaises(ShareUnavailable):
            space_document_delivery(
                user=self.recipient, delivery_id=next_delivery.pk,
            )
        fresh_delivery = share_space_document(
            actor=self.owner, version=version,
            recipient=self.recipient.profile, days=7,
        )
        archive_document(actor=self.owner, document=doc)
        with self.assertRaises(ShareUnavailable):
            space_document_delivery(
                user=self.recipient, delivery_id=fresh_delivery.pk,
            )

    def test_owner_share_cannot_leak_to_foreign_space(self):
        doc, version = self.create()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(
            f"{self.base}versions/{version.pk}/share/",
            {"recipient_username": self.recipient.username},
            format="json",
        ).status_code, 404)
        self.assertFalse(
            version.share_subjects.exists(),
        )

    def test_web_collection_detail_versions_and_sharing(self):
        from django.urls import reverse
        doc, version = self.create()
        self.client.force_login(self.owner)
        library_url = reverse(
            "organizations:space-documents", kwargs={"slug": self.space.slug},
        )
        response = self.client.get(library_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Statuts collectifs")
        self.assertContains(response, "Ajouter")
        detail_url = reverse(
            "organizations:space-document-detail",
            kwargs={"slug": self.space.slug, "document_id": doc.pk},
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Versions")
        self.assertContains(detail, "Partager")
        update_url = reverse(
            "organizations:space-document-update",
            kwargs={"slug": self.space.slug, "document_id": doc.pk},
        )
        self.assertEqual(self.client.post(update_url, {
            "title": "Statuts révisés", "visibility": "internal",
        }).status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Statuts révisés")
        share_url = reverse(
            "organizations:space-document-share",
            kwargs={"slug": self.space.slug, "document_id": doc.pk},
        )
        self.assertEqual(self.client.post(share_url, {
            "recipient": self.recipient.username, "days": 7,
        }).status_code, 302)
        self.assertEqual(version.share_subjects.count(), 1)
        archive_url = reverse(
            "organizations:space-document-archive",
            kwargs={"slug": self.space.slug, "document_id": doc.pk},
        )
        self.assertEqual(self.client.post(archive_url).status_code, 302)
        self.assertNotContains(self.client.get(library_url), "Statuts révisés")

    def test_space_read_permission_cannot_open_confidential_file(self):
        from authorization.constants import SystemRoleCode
        from authorization.services import grant_space_role
        public_user = User.objects.create_user(
            username="doc-space-marketing", password="x",
        )
        UserProfile.objects.get_or_create(user=public_user)
        grant_space_role(
            profile=public_user, space=self.space,
            role=SystemRoleCode.MARKETING, granted_by=self.owner,
        )
        restricted, restricted_version = self.create()
        internal, internal_version = self.create(visibility="internal")
        self.client.force_authenticate(public_user)
        docs = self.client.get(self.base)
        self.assertEqual(docs.status_code, 200, docs.data)
        self.assertEqual([item["id"] for item in docs.data["items"]], [
            str(internal.pk),
        ])
        self.assertEqual(self.client.get(
            f"{self.base}versions/{restricted_version.pk}/download/"
        ).status_code, 404)
        self.assertEqual(self.client.get(
            f"{self.base}versions/{internal_version.pk}/download/"
        ).status_code, 200)
        self.assertEqual(self.client.post(
            self.base,
            {"title": "Tentative", "file": pdf()},
            format="multipart",
        ).status_code, 404)

    def test_documents_owner_is_composed_into_nous_without_private_urls(self):
        doc, _ = self.create()
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/us/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        resources = response.data["resources"]
        self.assertEqual(resources["counts"]["document"], 1)
        self.assertEqual(resources["items"][0]["id"], str(doc.id))
        self.assertNotIn("private_media", str(resources))
        self.assertNotIn("content_hash", str(resources))
        self.assertNotIn("/download/", str(resources))

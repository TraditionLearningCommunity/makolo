"""Authenticated sharing owner receipts for multi-input Mark."""
import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from sharing.inbound_bundle_services import receive_inbound_bundle
from sharing.inbound_models import InboundCapture, InboundCaptureBundle
from core.api.mark_intake_views import (
    PersonalMarkIntakeAPIView, PersonalMarkReceiptAPIView,
    SpaceMarkIntakeAPIView, SpaceMarkReceiptAPIView,
)
from organizations.models import Organization
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role


def pdf():
    return SimpleUploadedFile(
        "facture.pdf", b"%PDF-1.4\nrecu\n", content_type="application/pdf",
    )


def audio():
    return SimpleUploadedFile(
        "voix.m4a", b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 64,
        content_type="audio/mp4",
    )


class MarkInboundBundleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="mark-intake-user", email="mark-intake@test.local", password="test",
        )
        self.other = User.objects.create_user(
            username="mark-intake-other", email="mark-other@test.local", password="test",
        )
        self.factory = APIRequestFactory()
        self.collection = PersonalMarkIntakeAPIView.as_view()

    def _post(self, *, key=None, files=None, text="", links=None, actor=None):
        key = key or uuid4().hex
        request = self.factory.post(
            "/api/v1/me/mark/intake/",
            data={
                "request_key": key,
                "text": text,
                "links": json.dumps(links or []),
                "context": json.dumps({}),
                "files": list(files or []),
            },
            format="multipart",
        )
        force_authenticate(request, user=actor or self.user)
        return self.collection(request)

    def test_media_only_and_mixed_receive_real_private_captures(self):
        first = self._post(files=[audio()])
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["data"]["state"], "received")
        self.assertEqual(first.data["data"]["file_count"], 1)
        self.assertFalse(first.data["data"]["action_confirmed"])
        bundle = InboundCaptureBundle.objects.get(pk=first.data["data"]["receipt_id"])
        self.assertEqual(bundle.created_by, self.user)
        self.assertEqual(bundle.captures.count(), 1)
        self.assertEqual(bundle.captures.first().mime_type, "audio/mp4")

        mixed = self._post(
            text="Préparer ma demande", files=[pdf(), audio()],
            links=["https://example.org/une-page"],
        )
        self.assertEqual(mixed.status_code, 201)
        self.assertEqual(mixed.data["data"]["file_count"], 2)
        self.assertEqual(mixed.data["data"]["capture_count"], 4)
        self.assertEqual(InboundCaptureBundle.objects.count(), 2)

    def test_retry_returns_same_receipt_and_rejects_changed_body(self):
        key = uuid4().hex
        first = self._post(key=key, files=[pdf()])
        second = self._post(key=key, files=[pdf()])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["data"]["receipt_id"], second.data["data"]["receipt_id"])
        self.assertEqual(InboundCapture.objects.count(), 1)
        changed = self._post(key=key, files=[audio()])
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(InboundCapture.objects.count(), 1)

    def test_unauthorized_and_foreign_receipts_do_not_leak(self):
        made = self._post(files=[pdf()])
        receipt_id = made.data["data"]["receipt_id"]
        get_view = PersonalMarkReceiptAPIView.as_view()
        request = self.factory.get(f"/api/v1/me/mark/intake/{receipt_id}/")
        force_authenticate(request, user=self.other)
        denied = get_view(request, receipt_id=receipt_id)
        self.assertEqual(denied.status_code, 404)

        request = self.factory.get("/api/v1/me/mark/intake/")
        force_authenticate(request, user=self.other)
        denied = self.collection(request)
        self.assertEqual(denied.status_code, 400)  # Missing request key.

    def test_receipt_lookup_by_stable_key(self):
        key = uuid4().hex
        made = self._post(key=key, files=[pdf()])
        request = self.factory.get(
            "/api/v1/me/mark/intake/", {"request_key": key},
        )
        force_authenticate(request, user=self.user)
        found = self.collection(request)
        self.assertEqual(found.data["data"]["receipt_id"], made.data["data"]["receipt_id"])

    def test_invalid_or_too_many_files_do_not_create_partial_receipt(self):
        result = self._post(files=[pdf(), SimpleUploadedFile(
            "bad.exe", b"malware", content_type="application/octet-stream",
        )])
        self.assertEqual(result.status_code, 400)
        self.assertFalse(InboundCaptureBundle.objects.exists())
        self.assertFalse(InboundCapture.objects.exists())
        result = self._post(files=[pdf() for _ in range(11)])
        self.assertEqual(result.status_code, 400)
        self.assertFalse(InboundCaptureBundle.objects.exists())

    def test_context_spoofing_and_private_links_are_rejected(self):
        self.assertEqual(
            self._post(links=["http://127.0.0.1/private"]).status_code,
            400,
        )
        request = self.factory.post("/api/v1/me/mark/intake/", data={
            "request_key": uuid4().hex,
            "text": "Une demande",
            "profile_id": "another-user",
        }, format="multipart")
        force_authenticate(request, user=self.user)
        self.assertEqual(self.collection(request).status_code, 400)
        self.assertFalse(InboundCaptureBundle.objects.exists())

    def test_space_receipt_requires_explicit_manage_authority(self):
        space = Organization.objects.create(
            name="Collectif de production", slug="collectif-mark-test",
            created_by=self.user,
        )
        grant_space_role(
            profile=self.user, space=space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.user,
        )
        path = f"/api/v1/organizations/workspaces/{space.slug}/mark/intake/"
        view = SpaceMarkIntakeAPIView.as_view()
        request = self.factory.post(
            path, data={
                "request_key": uuid4().hex,
                "text": "",
                "links": "[]",
                "context": "{}",
                "files": [pdf()],
            }, format="multipart",
        )
        force_authenticate(request, user=self.user)
        response = view(request, slug=space.slug)
        self.assertEqual(response.status_code, 201)
        receipt_id = response.data["data"]["receipt_id"]
        bundle = InboundCaptureBundle.objects.get(pk=receipt_id)
        self.assertEqual(bundle.space, space)
        self.assertFalse(response.data["data"]["action_confirmed"])

        foreign = self.factory.post(
            path, data={
                "request_key": uuid4().hex,
                "text": "Contenu privé",
            }, format="multipart",
        )
        force_authenticate(foreign, user=self.other)
        denied = view(foreign, slug=space.slug)
        self.assertIn(denied.status_code, (403, 404))

        lookup = SpaceMarkReceiptAPIView.as_view()
        foreign_lookup = self.factory.get(path + receipt_id + "/")
        force_authenticate(foreign_lookup, user=self.other)
        denied = lookup(foreign_lookup, slug=space.slug, receipt_id=receipt_id)
        self.assertIn(denied.status_code, (403, 404))

    def test_empty_request_is_not_a_receipt(self):
        self.assertEqual(self._post().status_code, 400)
        self.assertFalse(InboundCaptureBundle.objects.exists())

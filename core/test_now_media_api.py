from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core.api.now_media_views import PersonalNowJourneyArtifactMediaAPIView


class PersonalNowMediaAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.path = f"/api/v1/me/now/media/journey-artifacts/{uuid4()}/"
        self.artifact_id = uuid4()
        self.user = SimpleNamespace(is_authenticated=True, pk=uuid4())

    def _get(self, user=None):
        request = self.factory.get(self.path)
        if user is not False:
            force_authenticate(request, user=self.user if user is None else user)
        return PersonalNowJourneyArtifactMediaAPIView.as_view()(
            request, artifact_id=self.artifact_id,
        )

    @patch("core.api.now_media_views.artifact_for_download")
    def test_unauthenticated_request_never_fetches_media(self, lookup):
        response = self._get(user=False)
        self.assertIn(response.status_code, (401, 403))
        lookup.assert_not_called()

    @patch("core.api.now_media_views.artifact_for_download")
    def test_owner_authorization_is_rechecked_for_every_download(self, lookup):
        lookup.side_effect = PermissionDenied("not in case")
        response = self._get()
        self.assertEqual(response.status_code, 404)
        lookup.assert_called_once_with(
            actor=self.user, artifact_id=self.artifact_id,
        )

    @patch("core.api.now_media_views.artifact_for_download")
    def test_authorized_content_is_streamed_without_public_cache(self, lookup):
        lookup.return_value = SimpleNamespace(
            file=SimpleNamespace(open=lambda mode: ContentFile(b"%PDF-1.4\n")),
            mime_type="application/pdf",
        )
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Content-Disposition"], "inline")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\n")
        response.close()

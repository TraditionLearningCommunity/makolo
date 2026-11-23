"""Contract tests for opt-in Mark recorded-audio transcription."""
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.api.mark_audio_transcription_views import (
    PersonalMarkAudioTranscriptionAPIView,
)

URL = "/api/v1/me/mark/transcription/"


def fake_processor(audio):
    return "Texte extrait du fichier de test."


def empty_processor(audio):
    return ""


class MarkAudioTranscriptionContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PersonalMarkAudioTranscriptionAPIView.as_view()
        self.user = SimpleNamespace(pk=75101, is_authenticated=True)

    def request(self, method="get", **kwargs):
        call = getattr(self.factory, method)
        request = call(URL, **kwargs)
        force_authenticate(request, user=self.user)
        return self.view(request)

    @override_settings(MAKOLO_MARK_AUDIO_TRANSCRIBER="")
    def test_unconfigured_engine_is_not_offered_and_does_not_take_audio(self):
        status = self.request()
        self.assertEqual(status.status_code, 200)
        self.assertIs(status.data["data"]["available"], False)
        result = self.request(
            "post", data={"audio": SimpleUploadedFile(
                "voice.m4a", b"audio", content_type="audio/mp4")},
            format="multipart",
        )
        self.assertEqual(result.status_code, 503)

    @override_settings(MAKOLO_MARK_AUDIO_TRANSCRIBER=__name__ + ".fake_processor")
    def test_configured_processor_returns_text_without_a_business_action(self):
        status = self.request()
        self.assertIs(status.data["data"]["available"], True)
        result = self.request(
            "post", data={"audio": SimpleUploadedFile(
                "voice.m4a", b"recorded-data", content_type="audio/mp4")},
            format="multipart",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.data["data"]["text"], "Texte extrait du fichier de test."
        )
        self.assertEqual(result["Cache-Control"], "private, no-store")

    @override_settings(MAKOLO_MARK_AUDIO_TRANSCRIBER=__name__ + ".fake_processor")
    def test_rejects_non_audio_and_client_chosen_profile(self):
        invalid = self.request(
            "post", data={"audio": SimpleUploadedFile(
                "bad.txt", b"fake", content_type="text/plain")},
            format="multipart",
        )
        self.assertEqual(invalid.status_code, 415)
        forged = self.request(
            "post", data={
                "audio": SimpleUploadedFile(
                    "voice.m4a", b"audio", content_type="audio/mp4"),
                "profile_id": "another-profile",
            }, format="multipart",
        )
        self.assertEqual(forged.status_code, 400)

    @override_settings(MAKOLO_MARK_AUDIO_TRANSCRIBER=__name__ + ".empty_processor")
    def test_empty_recognition_is_not_claimed_as_success(self):
        result = self.request(
            "post", data={"audio": SimpleUploadedFile(
                "voice.m4a", b"audio", content_type="audio/mp4")},
            format="multipart",
        )
        self.assertEqual(result.status_code, 422)

    def test_anonymous_user_cannot_request_transcription(self):
        request = self.factory.get(URL)
        result = self.view(request)
        self.assertIn(result.status_code, (401, 403))

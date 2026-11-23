"""Provider adapter tests use mocks: no external API call and no real audio."""
import os
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core.mark_audio_openai_provider import (
    openai_audio_ready, transcribe_openai_recording,
)
from core.mark_audio_transcription import configured_mark_audio_transcriber


class MarkAudioOpenAIProviderTests(SimpleTestCase):
    @override_settings(MAKOLO_MARK_AUDIO_TRANSCRIBER="core.mark_audio_openai_provider.transcribe_openai_recording")
    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_no_key_means_no_advertised_capability(self):
        self.assertFalse(openai_audio_ready())
        self.assertIsNone(configured_mark_audio_transcriber())

    @override_settings(
        MAKOLO_MARK_AUDIO_TRANSCRIBER="core.mark_audio_openai_provider.transcribe_openai_recording",
        MAKOLO_MARK_AUDIO_MODEL="gpt-transcribe",
    )
    @patch.dict(os.environ, {"OPENAI_API_KEY": "server-only-test-secret"})
    @patch("core.mark_audio_openai_provider.requests.post")
    def test_only_real_response_text_is_returned(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {"text": "Bonjour depuis un enregistrement."}
        post.return_value = response
        self.assertIs(configured_mark_audio_transcriber(), transcribe_openai_recording)
        recorded = SimpleUploadedFile("enregistrement.m4a", b"fake-audio", content_type="audio/mp4")
        self.assertEqual(
            transcribe_openai_recording(recorded),
            "Bonjour depuis un enregistrement.",
        )
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/audio/transcriptions")
        self.assertEqual(kwargs["data"]["model"], "gpt-transcribe")
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["files"]["file"][0], "enregistrement.m4a")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "server-only-test-secret"})
    @patch("core.mark_audio_openai_provider.requests.post")
    def test_failed_provider_never_invents_a_transcript(self, post):
        post.return_value = Mock(status_code=429)
        recorded = SimpleUploadedFile("voice.webm", b"not-real-audio", content_type="audio/webm")
        with self.assertRaises(RuntimeError):
            transcribe_openai_recording(recorded)

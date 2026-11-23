"""Optional real recorded-audio transcription adapter.

Activate only with MAKOLO_MARK_AUDIO_TRANSCRIBER pointing to this callable
and an OPENAI_API_KEY configured on the server. Explicit "Transcrire" consent
is required upstream; recordings are never uploaded proactively by Makolo.
"""
import os

import requests
from django.conf import settings


_TRANSCRIPTION_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"


def openai_audio_ready():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def transcribe_openai_recording(uploaded_file):
    """Return only actual recognized words from the provider's JSON reply."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Audio transcription provider is not configured")
    name = getattr(uploaded_file, "name", "enregistrement.m4a")
    mime = getattr(uploaded_file, "content_type", "audio/mp4")
    uploaded_file.seek(0)
    try:
        response = requests.post(
            _TRANSCRIPTION_ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            data={"model": getattr(settings, "MAKOLO_MARK_AUDIO_MODEL", "gpt-transcribe")},
            files={"file": (name, uploaded_file, mime)},
            timeout=(5, 90),
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError("Recorded-audio transcription provider failed")
        data = response.json()
        words = data.get("text") if isinstance(data, dict) else None
        if not isinstance(words, str) or not words.strip():
            raise RuntimeError("Recorded-audio transcription returned no text")
        return words.strip()
    except (requests.RequestException, ValueError) as exc:
        # Never expose raw HTTP responses, provider keys or audio to the UI.
        raise RuntimeError("Recorded-audio transcription unavailable") from exc
    finally:
        uploaded_file.seek(0)


transcribe_openai_recording.is_configured = openai_audio_ready

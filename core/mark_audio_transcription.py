"""Optional owner-neutral file transcription adapter for Makolo Mark.

The server is authoritative for whether a real configured speech engine exists.
No media is stored here; the authenticated person explicitly submits a single
temporary audio file for a transcription, not for an action or a Requirement.
"""
from django.conf import settings
from django.utils.module_loading import import_string

MAX_MARK_AUDIO_BYTES = 25 * 1024 * 1024
MAX_MARK_TRANSCRIPT_CHARS = 20000
ACCEPTED_AUDIO_TYPES = frozenset({
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/wav",
    "audio/x-wav", "audio/webm", "audio/aac", "audio/mpeg",
})


def configured_mark_audio_transcriber():
    """Return a real configured callable or None. Never synthesize a response."""
    reference = getattr(settings, "MAKOLO_MARK_AUDIO_TRANSCRIBER", "")
    if not isinstance(reference, str) or not reference.strip():
        return None
    try:
        processor = import_string(reference.strip())
    except (ImportError, AttributeError, ValueError):
        return None
    if not callable(processor):
        return None
    availability = getattr(processor, "is_configured", None)
    if callable(availability):
        try:
            if not availability():
                return None
        except Exception:
            return None
    return processor

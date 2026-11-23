"""Shared technical validation of private recorded media.

This module has no Conversation, Journey or Questionnaire business ownership.
Authorization and storage remain with the canonical domain.
"""
import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_recorded_media(uploaded_file, kind):
    if uploaded_file is None:
        raise ValidationError("Un média est obligatoire.")
    bound = int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024))
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0 or size > bound:
        raise ValidationError("Taille de média non prise en charge.")
    mime = (getattr(uploaded_file, "content_type", "") or "").split(";", 1)[0].strip().lower()
    signatures = {
        "audio/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3") and b"A_OPUS" in b[:8192],
        "audio/ogg": lambda b: b.startswith(b"OggS") and (b"OpusHead" in b[:4096] or b"vorbis" in b[:4096]),
        "audio/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/x-m4a": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/wav": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE",
        "audio/mpeg": lambda b: b.startswith(b"ID3") or (len(b) > 2 and b[0] == 255 and b[1] & 0xE0 == 0xE0),
        "video/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "video/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
    }
    allowed = (
        {"video/mp4", "video/webm"} if kind == "video"
        else {"audio/webm", "audio/ogg", "audio/mp4", "audio/x-m4a", "audio/wav", "audio/mpeg"}
    )
    uploaded_file.seek(0)
    data = uploaded_file.read(bound + 1)
    uploaded_file.seek(0)
    if mime not in allowed or len(data) != size or not signatures[mime](data):
        raise ValidationError("Format ou signature du média non pris en charge.")
    return data, mime, hashlib.sha256(data).hexdigest()


def ensure_media_kind(kind, mime_type):
    if kind == "image" and not mime_type.startswith("image/"):
        raise ValidationError("Une image doit contenir un fichier image.")
    if kind in {"audio", "voice"} and not mime_type.startswith("audio/"):
        raise ValidationError("Un audio doit contenir un fichier audio.")
    if kind == "video" and not mime_type.startswith("video/"):
        raise ValidationError("Une vidéo doit contenir un fichier vidéo.")

from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


EVENT_COVER_MAX_SIZE = 8 * 1024 * 1024
EVENT_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
EVENT_COVER_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def validate_event_cover(uploaded_file) -> None:
    if uploaded_file.size > EVENT_COVER_MAX_SIZE:
        raise ValidationError("L’image de couverture ne peut pas dépasser 8 Mo.")

    filename = str(uploaded_file.name or "")
    if "/" in filename or "\\" in filename:
        raise ValidationError("Nom de fichier invalide.")
    extension = Path(filename).suffix.lower()
    if extension not in EVENT_COVER_EXTENSIONS:
        allowed = ", ".join(sorted(EVENT_COVER_EXTENSIONS))
        raise ValidationError(
            f"Extension non prise en charge. Extensions autorisées : {allowed}."
        )

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type.lower() not in EVENT_COVER_CONTENT_TYPES:
        raise ValidationError("Type de fichier image non pris en charge.")

    try:
        original_position = uploaded_file.tell()
    except (AttributeError, OSError):
        original_position = 0
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("L’image de couverture est invalide ou corrompue.") from exc
    finally:
        try:
            uploaded_file.seek(original_position)
        except (AttributeError, OSError):
            pass

from pathlib import Path

from django.core.exceptions import ValidationError


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

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in EVENT_COVER_EXTENSIONS:
        allowed = ", ".join(sorted(EVENT_COVER_EXTENSIONS))
        raise ValidationError(
            f"Extension non prise en charge. Extensions autorisées : {allowed}."
        )

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type.lower() not in EVENT_COVER_CONTENT_TYPES:
        raise ValidationError("Type de fichier image non pris en charge.")

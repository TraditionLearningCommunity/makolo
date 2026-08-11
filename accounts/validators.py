from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


AVATAR_MAX_SIZE = 5 * 1024 * 1024
VERIFICATION_DOCUMENT_MAX_SIZE = 10 * 1024 * 1024

AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

VERIFICATION_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
}
VERIFICATION_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def _safe_seek(uploaded_file, position=0):
    try:
        uploaded_file.seek(position)
    except (AttributeError, OSError):
        pass


def _verify_image(uploaded_file) -> None:
    try:
        original_position = uploaded_file.tell()
    except (AttributeError, OSError):
        original_position = 0
    try:
        _safe_seek(uploaded_file, 0)
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Le fichier image est invalide ou corrompu.") from exc
    finally:
        _safe_seek(uploaded_file, original_position)


def _verify_pdf(uploaded_file) -> None:
    try:
        original_position = uploaded_file.tell()
    except (AttributeError, OSError):
        original_position = 0
    try:
        _safe_seek(uploaded_file, 0)
        signature = uploaded_file.read(5)
    finally:
        _safe_seek(uploaded_file, original_position)
    if signature != b"%PDF-":
        raise ValidationError("Le document PDF est invalide ou corrompu.")


def validate_uploaded_file(
    uploaded_file,
    *,
    max_size: int,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
) -> str:
    if uploaded_file.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        raise ValidationError(
            f"File is too large. Maximum allowed size is {max_size_mb} MB."
        )

    filename = str(uploaded_file.name or "")
    if "/" in filename or "\\" in filename:
        raise ValidationError("Nom de fichier invalide.")
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            f"Unsupported file extension. Allowed extensions: {allowed}."
        )

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type.lower() not in allowed_content_types:
        raise ValidationError("Unsupported file type.")
    return extension


def validate_avatar(uploaded_file) -> None:
    validate_uploaded_file(
        uploaded_file,
        max_size=AVATAR_MAX_SIZE,
        allowed_extensions=AVATAR_EXTENSIONS,
        allowed_content_types=AVATAR_CONTENT_TYPES,
    )
    _verify_image(uploaded_file)


def validate_verification_document(uploaded_file) -> None:
    extension = validate_uploaded_file(
        uploaded_file,
        max_size=VERIFICATION_DOCUMENT_MAX_SIZE,
        allowed_extensions=VERIFICATION_DOCUMENT_EXTENSIONS,
        allowed_content_types=VERIFICATION_DOCUMENT_CONTENT_TYPES,
    )
    if extension == ".pdf":
        _verify_pdf(uploaded_file)
    else:
        _verify_image(uploaded_file)

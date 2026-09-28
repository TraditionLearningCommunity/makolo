from pathlib import Path
import re

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


MAKOLO_USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._]{1,28}[a-z0-9])?$")
MAKOLO_RESERVED_USERNAMES = {
    "admin",
    "api",
    "help",
    "login",
    "logout",
    "makolo",
    "me",
    "support",
    "system",
}


def normalize_makolo_username(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def validate_makolo_username(value: str) -> None:
    normalized = normalize_makolo_username(value)
    if len(normalized) < 3 or len(normalized) > 30:
        raise ValidationError("L’identifiant Makolo doit contenir entre 3 et 30 caractères.")
    if not MAKOLO_USERNAME_RE.fullmatch(normalized):
        raise ValidationError(
            "Utilisez uniquement des lettres minuscules, chiffres, points ou underscores, "
            "sans point ni underscore au début ou à la fin."
        )
    if normalized in MAKOLO_RESERVED_USERNAMES:
        raise ValidationError("Cet identifiant Makolo est réservé.")

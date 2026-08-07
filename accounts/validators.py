from pathlib import Path

from django.core.exceptions import ValidationError


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


def validate_uploaded_file(
    uploaded_file,
    *,
    max_size: int,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
) -> None:
    if uploaded_file.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        raise ValidationError(
            f"File is too large. Maximum allowed size is {max_size_mb} MB."
        )

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            f"Unsupported file extension. Allowed extensions: {allowed}."
        )

    content_type = getattr(uploaded_file, "content_type", None)
    if content_type and content_type.lower() not in allowed_content_types:
        raise ValidationError("Unsupported file type.")


def validate_avatar(uploaded_file) -> None:
    validate_uploaded_file(
        uploaded_file,
        max_size=AVATAR_MAX_SIZE,
        allowed_extensions=AVATAR_EXTENSIONS,
        allowed_content_types=AVATAR_CONTENT_TYPES,
    )


def validate_verification_document(uploaded_file) -> None:
    validate_uploaded_file(
        uploaded_file,
        max_size=VERIFICATION_DOCUMENT_MAX_SIZE,
        allowed_extensions=VERIFICATION_DOCUMENT_EXTENSIONS,
        allowed_content_types=VERIFICATION_DOCUMENT_CONTENT_TYPES,
    )

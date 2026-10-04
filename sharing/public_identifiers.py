from django.core.exceptions import ValidationError

from accounts.validators import MAKOLO_RESERVED_USERNAMES


def normalize_public_identifier(value):
    return (value or "").strip().lower()


def validate_public_identifier(value):
    normalized = normalize_public_identifier(value)
    if not normalized:
        raise ValidationError("L’identifiant public Makolo est obligatoire.")
    if normalized in MAKOLO_RESERVED_USERNAMES:
        raise ValidationError("Cet identifiant public Makolo est réservé.")
    return normalized

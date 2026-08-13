from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError


def normalize_country_code(value):
    return (value or "").strip().upper()


def validate_country_code(value):
    if not value:
        return
    normalized = normalize_country_code(value)
    if len(normalized) != 2 or not normalized.isascii() or not normalized.isalpha():
        raise ValidationError(
            "Le pays doit utiliser un code ISO 3166-1 alpha-2, par exemple CD ou KE."
        )


def validate_timezone_name(value):
    if not value:
        return
    try:
        ZoneInfo(value.strip())
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(
            "Utilisez une timezone IANA valide, par exemple Africa/Lubumbashi."
        ) from exc

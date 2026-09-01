from django.core.exceptions import ValidationError


PURPOSE_FIELDS = {
    "public_page": {"eyebrow": (str, 120), "intro": (str, 1200), "hero_image": (str, 500), "footer_note": (str, 500)},
    "invitation": {"eyebrow": (str, 120), "invitation_message": (str, 1600), "dress_code": (str, 300), "contact_text": (str, 500), "hero_image": (str, 500), "footer_note": (str, 500)},
    "access_pass": {"instructions": (str, 800), "hero_image": (str, 500), "footer_note": (str, 500)},
    "confirmation": {"intro": (str, 1000), "instructions": (str, 800), "footer_note": (str, 500)},
    "program": {"intro": (str, 1000), "footer_note": (str, 500)},
    "badge": {"eyebrow": (str, 120), "footer_note": (str, 300)},
}

FORBIDDEN_EDITORIAL_FIELDS = {
    "event_date", "event_time", "occurrence", "status", "location", "price", "payment_status",
    "access_status", "participant_identity", "credential", "capacity", "permission", "mandate",
}


def validate_editorial_data(purpose, data):
    if not isinstance(data, dict):
        raise ValidationError("Le contenu éditorial doit être un objet JSON.")
    allowed = PURPOSE_FIELDS.get(str(purpose), {})
    unknown = set(data) - set(allowed)
    forbidden = unknown & FORBIDDEN_EDITORIAL_FIELDS
    if forbidden:
        raise ValidationError(f"Champs métier interdits: {', '.join(sorted(forbidden))}.")
    if unknown:
        raise ValidationError(f"Champs éditoriaux inconnus: {', '.join(sorted(unknown))}.")
    for key, value in data.items():
        expected_type, max_length = allowed[key]
        if not isinstance(value, expected_type):
            raise ValidationError(f"{key} a un type invalide.")
        if len(value) > max_length:
            raise ValidationError(f"{key} dépasse {max_length} caractères.")

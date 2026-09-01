ALLOWED_BINDINGS = {
    "activity.display_title",
    "activity.description",
    "activity.kind",
    "occurrence.starts_at",
    "occurrence.ends_at",
    "occurrence.place",
    "organizer.display_name",
    "organizer.public_logo",
    "recipient.display_name",
    "access.display_type",
    "access.display_status",
    "access.beneficiary",
    "editorial.eyebrow",
    "editorial.intro",
    "editorial.invitation_message",
    "editorial.instructions",
    "editorial.dress_code",
    "editorial.contact_text",
    "editorial.signature",
    "editorial.hero_image",
    "editorial.footer_note",
    "actions.primary_url",
    "actions.primary_label",
}

SENSITIVE_SEGMENTS = {
    "password", "credential", "token", "cookie", "session", "mandate", "permission",
    "provider", "private_email", "metadata", "secret", "answers",
}


def binding_allowed(binding):
    if not isinstance(binding, str) or binding not in ALLOWED_BINDINGS:
        return False
    segments = set(binding.lower().split("."))
    return not segments.intersection(SENSITIVE_SEGMENTS)

import uuid

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import transaction

from .models import NotificationPreference, User, UserProfile
from .validators import normalize_makolo_username


def _provisional_username() -> str:
    while True:
        candidate = f"makolo_{uuid.uuid4().hex[:10]}"
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate


class MakoloSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Keep provider authentication separate from Makolo public identity."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.username = _provisional_username()
        user.username_configured = False

        email = (getattr(user, "email", "") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            # Equal e-mail is not authority to link two Makolo accounts.
            # Keep the new social identity separate and let an authenticated
            # user perform any future explicit linking flow.
            email = ""
        user.email = email or None
        return user

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        user.username = normalize_makolo_username(user.username)
        user.username_configured = False
        user.username_changed_at = None

        verified_emails = {
            (item.email or "").strip().lower()
            for item in getattr(sociallogin, "email_addresses", [])
            if getattr(item, "verified", False)
        }
        normalized_email = (user.email or "").strip().lower()
        user.email = normalized_email or None
        user.email_verified = bool(normalized_email and normalized_email in verified_emails)
        user.save(
            update_fields=[
                "username",
                "username_configured",
                "username_changed_at",
                "email",
                "email_verified",
                "updated_at",
            ]
        )

        UserProfile.objects.get_or_create(user=user)
        NotificationPreference.objects.get_or_create(user=user)
        return user

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import UserProfile


User = get_user_model()


class Task20AccountProductUxTests(TestCase):
    def test_new_profile_defaults_to_system_theme(self):
        user = User.objects.create_user(
            username="task20-theme",
            email="task20-theme@example.test",
            password="StrongPass2026!",
        )
        profile = UserProfile.objects.create(user=user)
        self.assertEqual(profile.theme, "system")

    def test_phone_accepts_common_formatting(self):
        user = User(
            username="task20-phone",
            email="task20-phone@example.test",
            phone="+243 (999) 000-111",
        )
        user.full_clean(exclude=["password"])

    def test_phone_rejects_invalid_characters_and_implausible_length(self):
        invalid_character = User(
            username="task20-phone-invalid",
            email="task20-phone-invalid@example.test",
            phone="+243 ABC 999",
        )
        with self.assertRaises(ValidationError):
            invalid_character.full_clean(exclude=["password"])

        invalid_length = User(
            username="task20-phone-short",
            email="task20-phone-short@example.test",
            phone="1234",
        )
        with self.assertRaises(ValidationError):
            invalid_length.full_clean(exclude=["password"])

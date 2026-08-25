from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.services import ensure_platform_admin_mandate
from organizations.services import create_organization


User = get_user_model()


class Task20LandingNavigationTests(TestCase):
    def test_participant_lands_in_personal_space(self):
        user = User.objects.create_user(
            username="task20-participant",
            email="task20-participant@example.test",
            password="StrongPass2026!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("core:participant-home"))

    def test_organizer_lands_in_personal_context_before_selecting_space(self):
        user = User.objects.create_user(
            username="task20-organizer",
            email="task20-organizer@example.test",
            password="StrongPass2026!",
        )
        create_organization(creator=user, name="Task 20 Space")
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("core:participant-home"))

    def test_django_staff_without_platform_authority_stays_personal(self):
        user = User.objects.create_user(
            username="task20-django-staff",
            email="task20-django-staff@example.test",
            password="StrongPass2026!",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("core:participant-home"))

    def test_platform_staff_lands_in_personal_context_before_operations(self):
        user = User.objects.create_user(
            username="task20-staff",
            email="task20-staff@example.test",
            password="StrongPass2026!",
            is_staff=True,
        )
        ensure_platform_admin_mandate(profile=user, source="task20-navigation-test")
        self.client.force_login(user)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("core:participant-home"))

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.device_accounts import DEVICE_COOKIE_NAME
from accounts.forms import AccountProfileForm
from accounts.models import UserDevice, UserProfile


User = get_user_model()
PASSWORD = "Task24-StrongPass!"


class Task24LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="task24-login",
            email="task24-login@example.test",
            password=PASSWORD,
        )

    def _login(self, **extra):
        payload = {"username": self.user.email, "password": PASSWORD, **extra}
        return self.client.post(reverse("core:login"), payload)

    def test_normal_login_uses_personal_context_and_sets_http_only_device_cookie(self):
        response = self._login()
        self.assertRedirects(response, reverse("core:participant-home"))
        cookie = response.cookies[DEVICE_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)

    def test_safe_next_is_respected(self):
        target = reverse("core:participant-accesses")
        response = self._login(next=target)
        self.assertRedirects(response, target)

    def test_external_next_is_never_followed(self):
        response = self._login(next="https://evil.example/steal")
        self.assertRedirects(response, reverse("core:participant-home"))


class Task24RememberedAccountTests(TestCase):
    def setUp(self):
        self.sarah = User.objects.create_user(
            username="task24-sarah",
            email="sarah-task24@example.test",
            first_name="Sarah",
            password=PASSWORD,
        )
        self.christophe = User.objects.create_user(
            username="task24-christophe",
            email="christophe-task24@example.test",
            first_name="Christophe",
            password=PASSWORD,
        )

    def _login(self, user, password=PASSWORD):
        return self.client.post(
            reverse("core:login"),
            {"username": user.email, "password": password},
        )

    def test_accounts_are_remembered_per_browser_without_authentication_grant(self):
        first = self._login(self.sarah)
        self.assertRedirects(first, reverse("core:participant-home"))
        device_cookie = self.client.cookies[DEVICE_COOKIE_NAME].value
        self.client.post(reverse("core:logout"))
        second = self._login(self.christophe)
        self.assertRedirects(second, reverse("core:participant-home"))
        self.assertEqual(self.client.cookies[DEVICE_COOKIE_NAME].value, device_cookie)

        response = self.client.get(reverse("account:switcher"))
        self.assertContains(response, "Sarah")
        self.assertContains(response, "Christophe")
        self.assertContains(response, "Mot de passe requis")
        self.assertNotContains(response, "session_key")
        self.assertEqual(UserDevice.objects.filter(device_key_hash__gt="").count(), 2)

    def test_switch_requires_reauthentication_and_rotates_session(self):
        self._login(self.sarah)
        self.client.post(reverse("core:logout"))
        self._login(self.christophe)
        previous_session = self.client.session.session_key

        response = self.client.post(reverse("account:switch-account", args=[self.sarah.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])
        self.assertIn("sarah-task24%40example.test", response["Location"])
        self.assertNotIn("password", response["Location"].lower())

        denied = self._login(self.sarah, password="wrong-password")
        self.assertEqual(denied.status_code, 200)
        self.assertFalse(denied.wsgi_request.user.is_authenticated)

        accepted = self._login(self.sarah)
        self.assertRedirects(accepted, reverse("core:participant-home"))
        self.assertNotEqual(self.client.session.session_key, previous_session)

    def test_unrelated_browser_cannot_enumerate_copied_device_cookie(self):
        self._login(self.sarah)
        copied = self.client.cookies[DEVICE_COOKIE_NAME].value

        other_client = self.client_class()
        other_client.force_login(self.christophe)
        other_client.cookies[DEVICE_COOKIE_NAME] = copied
        response = other_client.get(reverse("account:switcher"))
        self.assertNotContains(response, "Sarah")


class Task24ProfileFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="task24-profile",
            email="task24-profile@example.test",
            password=PASSWORD,
        )
        self.profile = UserProfile.objects.create(user=self.user)

    def _data(self, **overrides):
        data = {
            "first_name": "Sarah",
            "last_name": "Makolo",
            "phone": "+243 999 000 111",
            "birth_date": "",
            "gender": "female",
            "bio": "",
            "website": "",
            "linkedin_url": "",
            "facebook_url": "",
            "instagram_url": "",
            "x_url": "",
            "language": "fr",
            "timezone": "Africa/Lubumbashi",
            "company_name": "",
            "organization_name": "",
            "profession": "",
            "country": "",
            "city": "Lubumbashi",
            "address": "",
            "public_profile": "",
            "searchable": "",
        }
        data.update(overrides)
        return data

    def test_gender_language_and_timezone_are_controlled(self):
        valid = AccountProfileForm(self._data(), instance=self.user, profile=self.profile)
        self.assertTrue(valid.is_valid(), valid.errors)

        invalid_gender = AccountProfileForm(
            self._data(gender="free-text"), instance=self.user, profile=self.profile
        )
        self.assertFalse(invalid_gender.is_valid())
        self.assertIn("gender", invalid_gender.errors)

        invalid_language = AccountProfileForm(
            self._data(language="xx"), instance=self.user, profile=self.profile
        )
        self.assertFalse(invalid_language.is_valid())
        self.assertIn("language", invalid_language.errors)

        invalid_timezone = AccountProfileForm(
            self._data(timezone="Mars/Olympus_Mons"), instance=self.user, profile=self.profile
        )
        self.assertFalse(invalid_timezone.is_valid())
        self.assertIn("timezone", invalid_timezone.errors)

    def test_phone_validation_from_task20_remains_active(self):
        form = AccountProfileForm(
            self._data(phone="12"), instance=self.user, profile=self.profile
        )
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

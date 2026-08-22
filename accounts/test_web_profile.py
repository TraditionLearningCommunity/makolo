from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import NotificationPreference, UserProfile


User = get_user_model()


class AccountProfileWebTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile-user",
            email="profile@example.com",
            password="Strong-profile-password-2026!",
            first_name="Ancien",
        )

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("account:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_profile_page_creates_related_preferences_and_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mon profil")
        self.assertContains(response, "Apparence")
        self.assertContains(response, self.user.email)
        self.assertContains(response, "js/theme-preference.js")
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    def test_profile_update_updates_user_and_user_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:profile"),
            {
                "section": "profile",
                "first_name": "Gilbert",
                "last_name": "Makolo",
                "phone": "+243 999 000 111",
                "birth_date": "1995-04-12",
                "gender": "",
                "bio": "Participant et organisateur.",
                "website": "https://example.com",
                "linkedin_url": "",
                "facebook_url": "",
                "instagram_url": "",
                "x_url": "",
                "language": "fr",
                "timezone": "Africa/Lubumbashi",
                "company_name": "Makolo Labs",
                "organization_name": "Makolo",
                "profession": "Ingénieur",
                "country": "CD",
                "city": "Lubumbashi",
                "address": "Lubumbashi",
                "public_profile": "on",
                "searchable": "on",
            },
        )
        self.assertRedirects(response, reverse("account:profile"))
        self.user.refresh_from_db()
        profile = self.user.profile
        self.assertEqual(self.user.first_name, "Gilbert")
        self.assertEqual(self.user.last_name, "Makolo")
        self.assertEqual(profile.city, "Lubumbashi")
        self.assertEqual(profile.profession, "Ingénieur")
        self.assertTrue(profile.public_profile)
        self.assertTrue(profile.profile_completed)

    def test_profile_fields_use_browser_autocomplete_where_meaningful(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:profile"))
        self.assertContains(response, 'autocomplete="given-name"')
        self.assertContains(response, 'autocomplete="family-name"')
        self.assertContains(response, 'autocomplete="tel"')
        self.assertContains(response, 'autocomplete="address-level2"')

    def test_appearance_preference_uses_existing_profile_theme_and_renders_early(self):
        profile = UserProfile.objects.create(user=self.user, theme="system")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:profile"),
            {"section": "appearance", "appearance": "dark"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('account:profile')}#appearance")

        profile.refresh_from_db()
        self.assertEqual(profile.theme, "dark")
        self.user.refresh_from_db()
        self.assertNotIn("appearance", self.user.preferences)

        response = self.client.get(reverse("account:profile"))
        self.assertContains(response, 'data-theme-preference="dark"')
        self.assertContains(response, 'id="appearance-dark"')
        self.assertContains(response, 'aria-describedby="appearance-dark-help" checked')

    def test_invalid_appearance_is_rejected_without_overwriting_profile_theme(self):
        profile = UserProfile.objects.create(user=self.user, theme="light")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:profile"),
            {"section": "appearance", "appearance": "sepia"},
        )
        self.assertEqual(response.status_code, 400)
        profile.refresh_from_db()
        self.assertEqual(profile.theme, "light")
        self.assertContains(response, "Sélectionnez un choix valide", status_code=400)

    def test_notification_preferences_are_editable_without_overwriting_hidden_channels(self):
        preference = NotificationPreference.objects.create(
            user=self.user,
            sms_notifications=False,
            push_notifications=False,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account:profile"),
            {
                "section": "notifications",
                "email_notifications": "on",
                "security_notifications": "on",
                "event_notifications": "on",
                "quiet_hours_enabled": "on",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
            },
        )
        self.assertRedirects(response, reverse("account:profile"))
        preference.refresh_from_db()
        self.assertTrue(preference.email_notifications)
        self.assertFalse(preference.sms_notifications)
        self.assertFalse(preference.push_notifications)
        self.assertTrue(preference.quiet_hours_enabled)
        self.assertEqual(preference.quiet_hours_start.strftime("%H:%M"), "22:00")

    def test_password_change_is_reachable_from_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:password-change"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Changer le mot de passe")

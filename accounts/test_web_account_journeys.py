from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import NotificationPreference, UserProfile
from organizations.models import Organization, OrganizationMembership, OrganizationRole


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MAKOLO_PUBLIC_BASE_URL="https://makolo.test",
)
class WebAccountJourneyTests(TestCase):
    password = "Strong-web-account-password-2026!"

    def test_valid_web_registration_reuses_account_initialization(self):
        response = self.client.post(
            reverse("account:register"),
            {
                "email": "new.member@example.com",
                "username": "new-member",
                "first_name": "Nouveau",
                "last_name": "Membre",
                "phone": "+243 999 111 222",
                "password": self.password,
                "password_confirm": self.password,
            },
        )

        parsed = urlparse(response.url)
        self.assertEqual(parsed.path, reverse("core:login"))
        self.assertEqual(parse_qs(parsed.query).get("email"), ["new.member@example.com"])
        self.assertNotIn("password", parse_qs(parsed.query))
        user = User.objects.get(email="new.member@example.com")
        self.assertTrue(user.check_password(self.password))
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertTrue(NotificationPreference.objects.filter(user=user).exists())

    def test_invalid_web_registration_does_not_create_user(self):
        response = self.client.post(
            reverse("account:register"),
            {
                "email": "invalid.member@example.com",
                "username": "invalid-member",
                "password": self.password,
                "password_confirm": "Different-password-2026!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les mots de passe ne correspondent pas")
        self.assertFalse(User.objects.filter(email="invalid.member@example.com").exists())

    def test_forgot_password_is_generic_and_sends_reset_link_for_active_user(self):
        user = User.objects.create_user(
            username="forgot-web",
            email="forgot-web@example.com",
            password=self.password,
        )

        response = self.client.post(
            reverse("account:password-forgot"),
            {"email": user.email},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vérifiez votre boîte e-mail")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://makolo.test/account/password/reset/", mail.outbox[0].body)

        response_unknown = self.client.post(
            reverse("account:password-forgot"),
            {"email": "absent@example.com"},
        )
        self.assertEqual(response_unknown.status_code, 200)
        self.assertContains(response_unknown, "Vérifiez votre boîte e-mail")
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_accepts_valid_token_and_rejects_invalid_token(self):
        user = User.objects.create_user(
            username="reset-web",
            email="reset-web@example.com",
            password=self.password,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        new_password = "Another-strong-web-password-2026!"

        response = self.client.post(
            reverse(
                "account:password-reset-confirm",
                kwargs={"uid": uid, "token": token},
            ),
            {
                "new_password": new_password,
                "new_password_confirm": new_password,
            },
        )
        self.assertRedirects(response, reverse("core:login"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_password))

        invalid_response = self.client.post(
            reverse(
                "account:password-reset-confirm",
                kwargs={"uid": uid, "token": "invalid-token"},
            ),
            {
                "new_password": self.password,
                "new_password_confirm": self.password,
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "invalide ou expiré")

    def test_account_deletion_requires_explicit_confirmation_and_anonymizes(self):
        user = User.objects.create_user(
            username="delete-web",
            email="delete-web@example.com",
            password=self.password,
            first_name="Delete",
            last_name="Me",
        )
        self.client.force_login(user)

        missing_confirmation = self.client.post(
            reverse("account:delete"),
            {"password": self.password},
        )
        self.assertEqual(missing_confirmation.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        response = self.client.post(
            reverse("account:delete"),
            {"password": self.password, "confirm": "on"},
        )
        self.assertRedirects(response, reverse("core:home"))
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(user.email.endswith("@deleted.invalid"))
        self.assertEqual(user.first_name, "")

    def test_account_deletion_is_blocked_for_last_active_organization_owner(self):
        user = User.objects.create_user(
            username="sole-owner-web",
            email="sole-owner-web@example.com",
            password=self.password,
        )
        organization = Organization.objects.create(
            name="Sole Owner Organization",
            created_by=user,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationRole.OWNER,
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("account:delete"),
            {"password": self.password, "confirm": "on"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transférez d’abord la propriété")
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(
            OrganizationMembership.objects.get(
                organization=organization,
                user=user,
            ).is_active
        )

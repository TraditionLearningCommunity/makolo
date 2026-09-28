from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from allauth.socialaccount.models import SocialApp

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.validators import validate_verification_document


User = get_user_model()


class UserApiPermissionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="regular-user",
            email="regular@example.com",
            password="Strong-local-password-123!",
        )
        self.other_user = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="Strong-local-password-123!",
        )
        self.admin = User.objects.create_user(
            username="admin-user",
            email="admin@example.com",
            password="Strong-local-password-123!",
            is_staff=True,
        )

    def test_regular_user_cannot_list_all_users(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/accounts/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_access_another_user(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/accounts/users/{self.other_user.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_regular_user_can_update_own_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            f"/api/v1/accounts/users/{self.user.pk}/",
            {"first_name": "Makolo"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Makolo")

    def test_admin_can_list_users(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/accounts/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_detail_does_not_expose_internal_or_retired_authority_fields(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/accounts/users/{self.user.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in (
            "password",
            "failed_login_attempts",
            "account_locked_until",
            "metadata",
            "preferences",
            "settings_data",
            "analytics_data",
            "roles",
            "permission_groups",
            "is_organizer",
            "is_scanner_agent",
            "is_verified",
        ):
            self.assertNotIn(field, response.data)


class RegistrationValidationTests(APITestCase):
    def test_common_password_is_rejected(self):
        response = self.client.post(
            "/api/v1/accounts/auth/register/",
            {
                "email": "new@example.com",
                "username": "new-user",
                "password": "password123",
                "password_confirm": "password123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_registration_does_not_issue_jwt_tokens(self):
        response = self.client.post(
            "/api/v1/accounts/auth/register/",
            {
                "email": "safe@example.com",
                "username": "safe-user",
                "password": "Strong-registration-password-2026!",
                "password_confirm": "Strong-registration-password-2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIn("user", response.data)


class UploadValidationTests(APITestCase):
    def test_trust_evidence_validator_rejects_unsupported_extension(self):
        uploaded_file = SimpleUploadedFile(
            "identity.exe",
            b"not-a-real-document",
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            validate_verification_document(uploaded_file)



class MakoloIdentityFoundationTests(APITestCase):
    password = "Strong-local-password-2026!"

    def test_registration_accepts_identifier_without_email(self):
        response = self.client.post(
            "/api/v1/accounts/auth/register/",
            {
                "username": "sans-email",
                "password": self.password,
                "password_confirm": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="sans-email")
        self.assertIsNone(user.email)
        self.assertTrue(user.username_configured)
        self.assertIsNotNone(user.username_changed_at)

    def test_local_login_accepts_identifier_email_and_at_identifier(self):
        user = User.objects.create_user(
            username="kivu-runner",
            email="runner@example.com",
            password=self.password,
        )

        for login in ("kivu-runner", "@kivu-runner", "runner@example.com"):
            response = self.client.post(
                "/api/v1/accounts/auth/login/",
                {"username": login, "password": self.password},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, login)
            self.assertIn("access", response.data)
            self.assertIn("refresh", response.data)

        legacy_mobile = self.client.post(
            "/api/v1/accounts/auth/login/",
            {"email": "runner@example.com", "password": self.password},
            format="json",
        )
        self.assertEqual(legacy_mobile.status_code, status.HTTP_200_OK)
        self.assertIn("access", legacy_mobile.data)

        user.refresh_from_db()
        self.assertEqual(user.username, "kivu-runner")

    def test_identifier_availability_normalizes_and_rejects_reserved_values(self):
        User.objects.create_user(username="deja-pris", password=self.password)

        taken = self.client.get(
            "/api/v1/accounts/auth/identifier/availability/",
            {"value": "@DEJA-PRIS"},
        )
        self.assertEqual(taken.status_code, status.HTTP_200_OK)
        self.assertFalse(taken.data["available"])
        self.assertEqual(taken.data["username"], "deja-pris")

        reserved = self.client.get(
            "/api/v1/accounts/auth/identifier/availability/",
            {"value": "admin"},
        )
        self.assertEqual(reserved.status_code, status.HTTP_200_OK)
        self.assertFalse(reserved.data["available"])
        self.assertEqual(reserved.data["reason"], "invalid")

    def test_social_provisional_identifier_can_be_configured_then_enters_cooldown(self):
        user = User.objects.create_user(
            username="makolo_a1b2c3d4e5",
            password=self.password,
            username_configured=False,
            username_changed_at=None,
        )
        self.client.force_authenticate(user)

        first = self.client.patch(
            "/api/v1/accounts/auth/identifier/",
            {"username": "nouvel-identifiant"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.username, "nouvel-identifiant")
        self.assertTrue(user.username_configured)
        self.assertIsNotNone(user.username_changed_at)

        second = self.client.patch(
            "/api/v1/accounts/auth/identifier/",
            {"username": "encore-un"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", second.data)

    def test_email_is_unique_case_insensitively_when_present(self):
        User.objects.create_user(
            username="premier",
            email="Personne@Example.com",
            password=self.password,
        )
        response = self.client.post(
            "/api/v1/accounts/auth/register/",
            {
                "username": "second",
                "email": "personne@example.com",
                "password": self.password,
                "password_confirm": self.password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)


class PasswordResetRequestTests(APITestCase):
    def test_password_reset_request_reports_local_only_delivery_in_test_environment(self):
        user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Strong-local-password-123!",
        )
        self.assertIsNotNone(user.pk)

        response = self.client.post(
            "/api/v1/accounts/auth/password/forgot/",
            {"email": "reset@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email_delivery"], "local_only")
        self.assertIn("demande de réinitialisation", response.data["message"])

    def test_password_reset_request_does_not_reveal_account_existence(self):
        known = User.objects.create_user(
            username="known-reset-user",
            email="known-reset@example.com",
            password="Strong-local-password-123!",
        )
        self.assertIsNotNone(known.pk)

        known_response = self.client.post(
            "/api/v1/accounts/auth/password/forgot/",
            {"email": "known-reset@example.com"},
            format="json",
        )
        unknown_response = self.client.post(
            "/api/v1/accounts/auth/password/forgot/",
            {"email": "unknown-reset@example.com"},
            format="json",
        )

        self.assertEqual(known_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.status_code, status.HTTP_200_OK)
        self.assertEqual(known_response.data, unknown_response.data)


class SocialProviderStatusTests(APITestCase):
    endpoint = "/api/v1/accounts/auth/providers/"

    def _statuses(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {item["id"]: item for item in response.data["providers"]}

    def test_providers_are_unavailable_without_real_credentials(self):
        statuses = self._statuses()

        self.assertEqual(set(statuses), {"google", "facebook", "microsoft", "linkedin"})
        self.assertTrue(all(not item["configured"] for item in statuses.values()))

    def test_google_requires_non_empty_client_credentials(self):
        SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="",
            secret="",
        )
        self.assertFalse(self._statuses()["google"]["configured"])

        app = SocialApp.objects.get(provider="google")
        app.client_id = "test-google-client"
        app.secret = "test-google-secret"
        app.save(update_fields=["client_id", "secret"])
        self.assertTrue(self._statuses()["google"]["configured"])

    def test_linkedin_requires_oidc_identity_and_official_server(self):
        app = SocialApp.objects.create(
            provider="openid_connect",
            provider_id="linkedin",
            name="LinkedIn",
            client_id="test-linkedin-client",
            secret="test-linkedin-secret",
            settings={"server_url": "https://example.invalid"},
        )
        self.assertFalse(self._statuses()["linkedin"]["configured"])

        app.settings = {"server_url": "https://www.linkedin.com/oauth"}
        app.save(update_fields=["settings"])
        self.assertTrue(self._statuses()["linkedin"]["configured"])

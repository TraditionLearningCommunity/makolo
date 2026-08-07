from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.api.serializers import VerificationDocumentSerializer


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
        response = self.client.get(
            f"/api/v1/accounts/users/{self.other_user.pk}/"
        )
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

    def test_user_detail_does_not_expose_internal_security_fields(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"/api/v1/accounts/users/{self.user.pk}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in (
            "password",
            "failed_login_attempts",
            "account_locked_until",
            "metadata",
            "preferences",
            "settings_data",
            "analytics_data",
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
    def test_verification_document_rejects_unsupported_extension(self):
        uploaded_file = SimpleUploadedFile(
            "identity.exe",
            b"not-a-real-document",
            content_type="application/pdf",
        )
        serializer = VerificationDocumentSerializer(
            data={
                "document_type": "id_card",
                "file": uploaded_file,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

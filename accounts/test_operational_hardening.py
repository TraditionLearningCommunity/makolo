from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.services import request_password_reset
from accounts.validators import validate_avatar, validate_verification_document


User = get_user_model()


def _png_upload(name="avatar.png"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class UploadContentValidationTests(TestCase):
    def test_avatar_rejects_corrupt_image_with_valid_extension_and_mime(self):
        upload = SimpleUploadedFile(
            "avatar.png",
            b"not-a-real-image",
            content_type="image/png",
        )
        with self.assertRaises(ValidationError):
            validate_avatar(upload)

    def test_avatar_accepts_small_valid_image(self):
        validate_avatar(_png_upload())

    def test_verification_pdf_rejects_fake_pdf_signature(self):
        upload = SimpleUploadedFile(
            "identity.pdf",
            b"this-is-not-a-pdf",
            content_type="application/pdf",
        )
        with self.assertRaises(ValidationError):
            validate_verification_document(upload)


class PasswordResetOperationalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Strong-reset-password-2026!",
        )

    @override_settings(MAKOLO_PUBLIC_BASE_URL="https://beta.example.com")
    def test_reset_email_uses_public_base_url_without_duplicate_raw_token_fields(self):
        request_password_reset(email=self.user.email)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("https://beta.example.com/account/password/reset/", body)
        self.assertNotIn("makolo.smnasarl.com", body)
        self.assertNotIn("TOKEN:", body)
        self.assertNotIn("UID:", body)

    @patch(
        "accounts.services.mail.send_mail",
        side_effect=RuntimeError(
            "password=MAKOLO_PASSWORD_SECRET_MARKER token=MAKOLO_RESET_TOKEN_SECRET_MARKER"
        ),
    )
    def test_reset_email_backend_failure_does_not_expose_secrets_or_break_request(self, _send):
        with self.assertLogs("makolo", level="ERROR") as captured:
            request_password_reset(email=self.user.email)
        logged = "\n".join(captured.output)
        self.assertIn("Password reset email delivery failed user_id=", logged)
        self.assertNotIn("MAKOLO_PASSWORD_SECRET_MARKER", logged)
        self.assertNotIn("MAKOLO_RESET_TOKEN_SECRET_MARKER", logged)
        self.assertNotIn(self.user.email, logged)

    @patch("accounts.web_views.request_password_reset")
    def test_password_forgot_web_form_is_rate_limited(self, mocked_reset):
        for _ in range(5):
            response = self.client.post(
                "/account/password/forgot/",
                {"email": "target@example.com"},
                REMOTE_ADDR="203.0.113.20",
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/account/password/forgot/",
            {"email": "target@example.com"},
            REMOTE_ADDR="203.0.113.20",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(mocked_reset.call_count, 5)

    def test_web_login_is_rate_limited(self):
        for _ in range(10):
            response = self.client.post(
                "/login/",
                {"username": "target@example.com", "password": "wrong-password"},
                REMOTE_ADDR="203.0.113.21",
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/login/",
            {"username": "target@example.com", "password": "wrong-password"},
            REMOTE_ADDR="203.0.113.21",
        )
        self.assertEqual(response.status_code, 429)

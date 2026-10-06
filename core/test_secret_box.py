from django.test import SimpleTestCase, override_settings

from core.secret_box import decrypt_runtime_secret, encrypt_runtime_secret


class RuntimeSecretBoxTests(SimpleTestCase):
    @override_settings(SECRET_KEY="current-secret", SECRET_KEY_FALLBACKS=[])
    def test_round_trip(self):
        encrypted = encrypt_runtime_secret("push-token-value")
        self.assertNotIn("push-token-value", encrypted)
        self.assertEqual(decrypt_runtime_secret(encrypted), "push-token-value")

    def test_previous_key_can_decrypt_during_rotation(self):
        with override_settings(SECRET_KEY="old-secret", SECRET_KEY_FALLBACKS=[]):
            encrypted = encrypt_runtime_secret("rotating-token")
        with override_settings(
            SECRET_KEY="new-secret",
            SECRET_KEY_FALLBACKS=["old-secret"],
        ):
            self.assertEqual(decrypt_runtime_secret(encrypted), "rotating-token")

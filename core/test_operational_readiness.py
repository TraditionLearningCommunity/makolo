import io
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from core.logging_filters import redact_sensitive_text


class HealthReadinessTests(TestCase):
    def test_health_remains_lightweight_liveness(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_checks_database(self):
        response = self.client.get("/api/v1/readiness/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    @patch("core.api.views.connection.cursor", side_effect=DatabaseError("db-password=secret"))
    def test_readiness_hides_database_failure_details(self, _cursor):
        response = self.client.get("/api/v1/readiness/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn("secret", response.content.decode("utf-8"))


class LoggingRedactionTests(SimpleTestCase):
    def test_common_secrets_and_password_reset_tokens_are_redacted(self):
        value = (
            "GET /account/password-reset/MQ/raw-reset-token/ "
            "Authorization: Bearer ey.secret.jwt password=hunter2 token=abc123"
        )
        redacted = redact_sensitive_text(value)
        self.assertNotIn("raw-reset-token", redacted)
        self.assertNotIn("ey.secret.jwt", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertIn("[redacted]", redacted)


class OperationalSettingsTests(SimpleTestCase):
    def _production_env(self):
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_ENV": "production",
                "DJANGO_DEBUG": "False",
                "DJANGO_SECRET_KEY": "production-test-secret-key-with-enough-entropy-only-for-ci",
                "DJANGO_ALLOWED_HOSTS": "beta.example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://beta.example.com",
                "MAKOLO_PUBLIC_BASE_URL": "https://beta.example.com",
                "PAYMENTS_SANDBOX_ENABLED": "False",
            }
        )
        return env

    def _import_settings(self, env):
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_refuses_missing_secret_key(self):
        env = self._production_env()
        env.pop("DJANGO_SECRET_KEY", None)
        result = self._import_settings(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_production_refuses_missing_public_base_url(self):
        env = self._production_env()
        env.pop("MAKOLO_PUBLIC_BASE_URL", None)
        result = self._import_settings(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MAKOLO_PUBLIC_BASE_URL", result.stderr)

    def test_production_refuses_insecure_public_base_url(self):
        env = self._production_env()
        env["MAKOLO_PUBLIC_BASE_URL"] = "http://beta.example.com"
        result = self._import_settings(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTPS", result.stderr)

    def test_static_and_media_roots_are_separate(self):
        self.assertNotEqual(Path(settings.STATIC_ROOT).resolve(), Path(settings.MEDIA_ROOT).resolve())


@skipUnless(connection.vendor == "sqlite", "SQLite backup command is SQLite-specific")
class BackupDatabaseTests(TransactionTestCase):
    reset_sequences = False

    def test_backup_database_creates_integrity_checked_database(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            call_command("backup_database", output_dir=directory, stdout=output)
            backup_path = Path(output.getvalue().strip().splitlines()[-1])
            self.assertTrue(backup_path.exists())
            self.assertGreater(backup_path.stat().st_size, 0)

            restored = sqlite3.connect(backup_path)
            try:
                integrity = restored.execute("PRAGMA integrity_check").fetchone()
                account_table = restored.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts_user'"
                ).fetchone()
            finally:
                restored.close()
            self.assertEqual(integrity, ("ok",))
            self.assertEqual(account_table, ("accounts_user",))

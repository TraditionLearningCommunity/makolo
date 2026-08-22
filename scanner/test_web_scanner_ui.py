from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility


User = get_user_model()


class ScannerWebUiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="scanner-ui-staff",
            email="scanner-ui@example.com",
            password="Strong-scanner-password-2026!",
            is_staff=True,
        )
        start_at = timezone.now() + timedelta(days=2)
        self.event = Event.objects.create(
            organizer=self.staff,
            title="Scanner Web Test",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=3),
            published_at=timezone.now(),
        )

    def test_scanner_console_exposes_camera_image_and_manual_fallbacks(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("scanner:console", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dist/qr-scanner.umd.min.js")
        self.assertContains(response, "dist/scanner.js")
        self.assertNotContains(response, "cdn.jsdelivr.net")
        self.assertContains(response, "Démarrer la caméra")
        self.assertContains(response, "Lire un QR depuis une image")
        self.assertContains(response, "Code du billet")
        self.assertContains(response, "Vérifier le billet")
        self.assertContains(response, "data-scan-url")

        scanner_source = (Path(settings.BASE_DIR) / "frontend" / "src" / "scanner.js").read_text(encoding="utf-8")
        self.assertIn("QrScanner.scanImage", scanner_source)
        self.assertIn("QrScanner.listCameras", scanner_source)
        self.assertIn("qrScanner.toggleFlash", scanner_source)
        self.assertIn("BarcodeDetector", scanner_source)

    def test_scanner_console_requires_authentication(self):
        response = self.client.get(reverse("scanner:console", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

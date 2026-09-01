from base64 import b64decode
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from PIL import Image

from core.branding import render_makolo_qr_data_uri, render_makolo_qr_png


class ProductBrandingContractTests(SimpleTestCase):
    payload = "makolo:test:opaque-signed-payload"

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_branded_qr_is_a_valid_png_with_reasonable_size(self):
        png = render_makolo_qr_png(self.payload, branded=True, box_size=6)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        image = Image.open(BytesIO(png))
        self.assertEqual(image.format, "PNG")
        self.assertGreaterEqual(image.width, 180)
        self.assertEqual(image.width, image.height)

    def test_unbranded_qr_remains_available(self):
        png = render_makolo_qr_png(self.payload, branded=False, box_size=6)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_branding_failure_falls_back_to_plain_high_correction_qr(self):
        with patch("core.branding._load_mark_geometry", side_effect=FileNotFoundError("mark")):
            png = render_makolo_qr_png(self.payload, branded=True, box_size=6)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        image = Image.open(BytesIO(png))
        self.assertEqual(image.size[0], image.size[1])

    def test_data_uri_contains_only_png_representation(self):
        uri = render_makolo_qr_data_uri(self.payload, box_size=6)
        prefix, encoded = uri.split(",", 1)
        self.assertEqual(prefix, "data:image/png;base64")
        self.assertTrue(b64decode(encoded).startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertNotIn(self.payload, uri)

    def test_access_surface_uses_canonical_qr_tag_and_official_mark(self):
        source = self._source("templates/core/participant_access_detail.html")
        self.assertIn("makolo_access_qr credential as makolo_qr", source)
        self.assertIn("partials/brand_mark.html", source)
        self.assertIn("QR Makolo", source)
        self.assertNotIn("{{ qr_data }}", source)

    def test_shared_mark_and_empty_state_use_official_asset(self):
        mark = self._source("templates/partials/brand_mark.html")
        empty = self._source("templates/partials/brand_empty.html")
        self.assertIn("brand/makolo-mark-ink.svg", mark)
        self.assertIn("partials/brand_mark.html", empty)

    def test_motion_respects_reduced_motion(self):
        css = self._source("static/css/makolo-brand-assets.css")
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertIn(".mk-brand-enter", css)

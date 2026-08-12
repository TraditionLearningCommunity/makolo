from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


OFFICIAL_ASSETS = (
    "brand/makolo-mark-gradient.svg",
    "brand/makolo-mark-white.svg",
    "brand/makolo-mark-violet.svg",
    "brand/makolo-mark-ink.svg",
    "brand/makolo-logo-light.svg",
    "brand/makolo-logo-dark.svg",
    "brand/favicon.svg",
    "brand/favicon.ico",
    "brand/apple-touch-icon.png",
)


class BrandAssetContractTests(SimpleTestCase):
    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_official_assets_are_discoverable(self):
        for asset in OFFICIAL_ASSETS:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

    def test_browser_icons_keep_expected_binary_signatures(self):
        ico_path = finders.find("brand/favicon.ico")
        png_path = finders.find("brand/apple-touch-icon.png")
        self.assertIsNotNone(ico_path)
        self.assertIsNotNone(png_path)
        self.assertTrue(Path(ico_path).read_bytes().startswith(b"\x00\x00\x01\x00"))
        self.assertTrue(Path(png_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_shared_brand_head_declares_browser_icons(self):
        source = self._source("templates/partials/brand_head.html")
        self.assertIn("brand/favicon.svg", source)
        self.assertIn("brand/favicon.ico", source)
        self.assertIn("brand/apple-touch-icon.png", source)

        for template in (
            "templates/base/app.html",
            "templates/base/public.html",
            "templates/base/auth.html",
        ):
            with self.subTest(template=template):
                self.assertIn("partials/brand_head.html", self._source(template))

    def test_public_header_switches_official_logo_with_theme(self):
        source = self._source("templates/base/public.html")
        self.assertIn("brand/makolo-logo-light.svg", source)
        self.assertIn("brand/makolo-logo-dark.svg", source)
        self.assertIn("mk-brand-lockup-light", source)
        self.assertIn("mk-brand-lockup-dark", source)

    def test_application_surfaces_use_official_mark_variants(self):
        sidebar = self._source("templates/partials/sidebar.html")
        auth = self._source("templates/base/auth.html")
        self.assertIn("brand/makolo-mark-violet.svg", sidebar)
        self.assertIn("brand/makolo-mark-white.svg", sidebar)
        self.assertIn("brand/makolo-mark-white.svg", auth)
        self.assertIn("brand/makolo-mark-gradient.svg", auth)

    def test_legacy_fake_m_brand_rule_is_removed(self):
        css = self._source("static/css/makolo-brand.css")
        self.assertNotIn(".mk-brand-mark {", css)

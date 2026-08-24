from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse


class DiscoveryProductUxTests(SimpleTestCase):
    def test_discovery_uses_human_timezone_copy_and_external_ux_asset(self):
        response = self.client.get(reverse("discovery:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les horaires sont affichés dans l’heure locale des activités.")
        self.assertContains(response, "js/discovery-ux.js")
        self.assertNotContains(response, "Dates interprétées dans Africa/")

    def test_map_failure_keeps_discovery_usable_without_network(self):
        script = (Path(settings.BASE_DIR) / "static" / "js" / "discovery-ux.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("map.on('error', failGracefully)", script)
        self.assertIn("container.classList.add('hidden')", script)
        self.assertIn("fallback.classList.remove('hidden')", script)
        self.assertIn("listButton.click()", script)
        self.assertNotIn("fetch(", script)

    def test_geolocation_precision_is_limited_before_search_submission(self):
        script = (Path(settings.BASE_DIR) / "static" / "js" / "discovery-ux.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("value.toFixed(4)", script)

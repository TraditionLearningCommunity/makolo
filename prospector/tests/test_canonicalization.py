from unittest import TestCase

from prospector.canonicalization import canonicalize_locator, canonicalize_web_url
from prospector.errors import ProspectorContractError, UnsupportedTargetKindError


class WebUrlCanonicalizationTests(TestCase):
    def test_normalizes_scheme_host_default_port_and_fragment(self):
        self.assertEqual(
            canonicalize_web_url(" HTTPS://Example.COM:443/path?q=1#fragment "),
            "https://example.com/path?q=1",
        )

    def test_empty_path_becomes_root(self):
        self.assertEqual(canonicalize_web_url("http://example.com"), "http://example.com/")

    def test_query_is_preserved_without_policy_guessing(self):
        self.assertEqual(
            canonicalize_web_url(
                "https://example.com/jobs?utm_source=x&id=7&utm_source=y"
            ),
            "https://example.com/jobs?utm_source=x&id=7&utm_source=y",
        )

    def test_unicode_hostname_is_idna_canonicalized(self):
        self.assertEqual(
            canonicalize_web_url("https://éxample.test/path"),
            "https://xn--xample-9ua.test/path",
        )

    def test_embedded_credentials_are_rejected(self):
        with self.assertRaises(ProspectorContractError):
            canonicalize_web_url("https://user:secret@example.com/path")

    def test_relative_and_non_http_targets_are_rejected(self):
        for value in ("/relative", "ftp://example.com/file"):
            with self.subTest(value=value), self.assertRaises(ProspectorContractError):
                canonicalize_web_url(value)

    def test_equivalent_urls_produce_same_versioned_target_key(self):
        left = canonicalize_locator(
            kind="web_url",
            locator="https://EXAMPLE.com:443/programs#section",
        )
        right = canonicalize_locator(
            kind="web_url",
            locator="https://example.com/programs",
        )
        self.assertEqual(left.locator, right.locator)
        self.assertEqual(left.target_key, right.target_key)
        self.assertTrue(left.target_key.startswith("web_url:v1:"))

    def test_unknown_kind_is_explicitly_unsupported(self):
        with self.assertRaises(UnsupportedTargetKindError):
            canonicalize_locator(kind="api_endpoint", locator="https://example.com/api")

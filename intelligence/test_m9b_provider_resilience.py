import urllib.error
from unittest.mock import patch

from django.test import SimpleTestCase

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest
from intelligence.exceptions import InvalidProviderResult, ProviderUnavailable
from intelligence.providers.openai_compatible import OpenAICompatibleProvider


class _RawResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class OpenAICompatibleResilienceTests(SimpleTestCase):
    def setUp(self):
        self.provider = OpenAICompatibleProvider(
            key="m9b-test",
            base_url="https://provider.example.test/v1",
            api_key="test-key-not-a-secret",
            model="test-model",
            timeout_seconds=3,
        )
        self.request = IntelligenceRequest(
            capability=IntelligenceCapability.TEXT_GENERATE,
            input={"text": "test"},
        )

    def test_connection_failure_is_controlled_and_not_retried(self):
        with patch(
            "intelligence.providers.openai_compatible._open_url",
            side_effect=urllib.error.URLError("connection refused"),
        ) as opener:
            with self.assertRaisesRegex(ProviderUnavailable, "network_unavailable"):
                self.provider.execute(self.request)
        opener.assert_called_once()

    def test_non_success_http_response_is_classified_and_not_retried(self):
        error = urllib.error.HTTPError(
            self.provider.base_url,
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )
        with patch(
            "intelligence.providers.openai_compatible._open_url",
            side_effect=error,
        ) as opener:
            with self.assertRaisesRegex(ProviderUnavailable, "http_503"):
                self.provider.execute(self.request)
        opener.assert_called_once()

    def test_malformed_response_is_rejected(self):
        with patch(
            "intelligence.providers.openai_compatible._open_url",
            return_value=_RawResponse(b"{not-json"),
        ):
            with self.assertRaisesRegex(InvalidProviderResult, "invalid_json"):
                self.provider.execute(self.request)

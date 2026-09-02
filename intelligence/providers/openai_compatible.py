from __future__ import annotations

import json
import urllib.error
import urllib.request

from intelligence.capabilities import IntelligenceCapability
from intelligence.contracts import IntelligenceRequest, IntelligenceResult
from intelligence.exceptions import CapabilityUnsupported, InvalidProviderResult, ProviderUnavailable

from .base import IntelligenceProvider


class OpenAICompatibleProvider(IntelligenceProvider):
    capabilities = frozenset(
        {
            IntelligenceCapability.TEXT_GENERATE,
            IntelligenceCapability.STRUCTURED_GENERATE,
            IntelligenceCapability.EMBED,
        }
    )

    def __init__(self, *, key: str, base_url: str, api_key: str, model: str, timeout_seconds: int = 8):
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderUnavailable("invalid_credentials") from exc
            raise ProviderUnavailable(f"http_{exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailable("network_unavailable") from exc
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise InvalidProviderResult("invalid_json") from exc
        if not isinstance(value, dict):
            raise InvalidProviderResult("invalid_payload")
        return value

    def execute(self, request: IntelligenceRequest) -> IntelligenceResult:
        if request.capability == IntelligenceCapability.EMBED:
            texts = request.input.get("texts")
            if not isinstance(texts, list) or not all(isinstance(item, str) for item in texts):
                raise InvalidProviderResult("embed_input_invalid")
            payload = self._post("/embeddings", {"model": self.model, "input": texts})
            data = payload.get("data")
            if not isinstance(data, list):
                raise InvalidProviderResult("embed_output_invalid")
            vectors = [item.get("embedding") for item in data if isinstance(item, dict)]
            if len(vectors) != len(texts):
                raise InvalidProviderResult("embed_output_invalid")
            return IntelligenceResult(available=True, output=vectors, provider_key=self.key, model=self.model)

        if request.capability not in {
            IntelligenceCapability.TEXT_GENERATE,
            IntelligenceCapability.STRUCTURED_GENERATE,
        }:
            raise CapabilityUnsupported(request.capability.value)

        messages = request.input.get("messages")
        if not isinstance(messages, list):
            text = request.input.get("text", "")
            messages = [{"role": "user", "content": str(text)}]
        payload = {"model": self.model, "messages": messages}
        if request.capability == IntelligenceCapability.STRUCTURED_GENERATE:
            payload["response_format"] = {"type": "json_object"}
        result = self._post("/chat/completions", payload)
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidProviderResult("completion_output_invalid") from exc
        if request.capability == IntelligenceCapability.STRUCTURED_GENERATE:
            try:
                content = json.loads(content)
            except (TypeError, json.JSONDecodeError) as exc:
                raise InvalidProviderResult("structured_output_invalid") from exc
        return IntelligenceResult(available=True, output=content, provider_key=self.key, model=self.model)

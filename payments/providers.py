from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .models import PaymentProvider


@dataclass(frozen=True)
class ProviderCompletion:
    provider_reference: str
    source: str


class PaymentProviderAdapter:
    """Minimal provider boundary owned by Payments.

    Real providers can later implement network initiation/event confirmation without
    changing PaymentObligation, Journey or Commerce contracts.
    """

    code: str

    def completion(self, *, payment, provider_reference: str = "", source: str = "provider") -> ProviderCompletion:
        reference = (provider_reference or "").strip()
        if not reference:
            raise ValidationError("La référence fournisseur est obligatoire.")
        return ProviderCompletion(provider_reference=reference, source=source)


class SandboxProviderAdapter(PaymentProviderAdapter):
    code = PaymentProvider.SANDBOX

    def completion(self, *, payment, provider_reference: str = "", source: str = "sandbox-ui") -> ProviderCompletion:
        reference = (provider_reference or "").strip() or f"SBX-{uuid.uuid4().hex[:20].upper()}"
        return ProviderCompletion(provider_reference=reference, source=source)


class ManualProviderAdapter(PaymentProviderAdapter):
    code = PaymentProvider.MANUAL

    def completion(self, *, payment, provider_reference: str = "", source: str = "manual") -> ProviderCompletion:
        reference = (provider_reference or "").strip() or f"MAN-{uuid.uuid4().hex[:20].upper()}"
        return ProviderCompletion(provider_reference=reference, source=source)


_ADAPTERS = {
    PaymentProvider.SANDBOX: SandboxProviderAdapter(),
    PaymentProvider.MANUAL: ManualProviderAdapter(),
}


def get_provider_adapter(provider: str) -> PaymentProviderAdapter:
    try:
        return _ADAPTERS[provider]
    except KeyError as exc:
        raise ValidationError("Fournisseur de paiement non pris en charge.") from exc

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .models import PaymentProvider


@dataclass(frozen=True)
class ProviderInitiation:
    checkout_url: str = ""


@dataclass(frozen=True)
class ProviderCompletion:
    provider_reference: str
    source: str


@dataclass(frozen=True)
class ProviderRefund:
    provider_reference: str


class PaymentProviderAdapter:
    """Minimal provider boundary owned by Payments.

    The domain owns obligations and payment lifecycle. Adapters only encapsulate
    provider-specific initiation/confirmation/cancellation/refund mechanics.
    Future real providers can implement this contract without leaking provider
    conditions into Commerce, Journey or Services.
    """

    code: str

    def initiate(self, *, payment) -> ProviderInitiation:
        return ProviderInitiation()

    def confirm(self, *, payment, provider_reference: str = "", source: str = "provider") -> ProviderCompletion:
        reference = (provider_reference or "").strip()
        if not reference:
            raise ValidationError("La référence fournisseur est obligatoire.")
        return ProviderCompletion(provider_reference=reference, source=source)

    def cancel(self, *, payment) -> None:
        return None

    def refund(self, *, payment, amount) -> ProviderRefund:
        return ProviderRefund(provider_reference=f"RFD-{self.code.upper()}-{uuid.uuid4().hex[:16].upper()}")


class SandboxProviderAdapter(PaymentProviderAdapter):
    code = PaymentProvider.SANDBOX

    def confirm(self, *, payment, provider_reference: str = "", source: str = "sandbox-ui") -> ProviderCompletion:
        reference = (provider_reference or "").strip() or f"SBX-{uuid.uuid4().hex[:20].upper()}"
        return ProviderCompletion(provider_reference=reference, source=source)


class ManualProviderAdapter(PaymentProviderAdapter):
    code = PaymentProvider.MANUAL

    def confirm(self, *, payment, provider_reference: str = "", source: str = "manual") -> ProviderCompletion:
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

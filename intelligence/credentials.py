from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .models import ProviderConnection, ProviderCredential


def _fernet() -> Fernet:
    raw = os.environ.get("INTELLIGENCE_CREDENTIAL_MASTER_KEY", "").strip()
    if not raw:
        raise ImproperlyConfigured(
            "INTELLIGENCE_CREDENTIAL_MASTER_KEY doit être définie pour stocker ou lire des credentials Intelligence."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())
    return Fernet(key)


def _hint(secret: str) -> str:
    value = secret.strip()
    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}••••{value[-4:]}"


def set_provider_secret(*, connection: ProviderConnection, secret: str) -> ProviderCredential:
    value = secret.strip()
    if not value:
        raise ValueError("Le credential provider ne peut pas être vide.")
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    credential, created = ProviderCredential.objects.update_or_create(
        connection=connection,
        defaults={
            "encrypted_secret": encrypted,
            "key_hint": _hint(value),
            "rotated_at": None if not ProviderCredential.objects.filter(connection=connection).exists() else timezone.now(),
        },
    )
    return credential


def get_provider_secret(*, connection: ProviderConnection) -> str:
    try:
        credential = connection.credential
    except ProviderCredential.DoesNotExist as exc:
        raise ValueError("Aucun credential configuré pour cette connexion.") from exc
    try:
        return _fernet().decrypt(credential.encrypted_secret.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ImproperlyConfigured("Impossible de déchiffrer le credential Intelligence.") from exc

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


_CONTEXT = b"makolo-runtime-secret-v1"


def _fernet_for(secret_key: str) -> Fernet:
    material = _CONTEXT + b":" + secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)


def encrypt_runtime_secret(value: str) -> str:
    secret = value.strip()
    if not secret:
        raise ValueError("Le secret runtime ne peut pas être vide.")
    return _fernet_for(settings.SECRET_KEY).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_runtime_secret(value: str) -> str:
    token = value.encode("ascii")
    candidates = [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return _fernet_for(candidate).decrypt(token).decode("utf-8")
        except InvalidToken:
            continue
    raise ImproperlyConfigured(
        "Impossible de déchiffrer un secret runtime avec SECRET_KEY ou ses fallbacks."
    )

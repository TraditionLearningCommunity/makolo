from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.secret_box import decrypt_runtime_secret, encrypt_runtime_secret

from .models import PushEndpoint, PushPlatform, PushProvider
from .navigation import build_notification_navigation


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _token_hint(token: str) -> str:
    value = token.strip()
    if len(value) <= 12:
        return "••••"
    return f"{value[:4]}••••{value[-6:]}"


@transaction.atomic
def register_push_endpoint(
    *,
    user,
    provider: str,
    platform: str,
    installation_id: str,
    token: str,
    app_version: str = "",
) -> PushEndpoint:
    provider = (provider or "").strip().lower()
    platform = (platform or "").strip().lower()
    installation_id = (installation_id or "").strip()
    token = (token or "").strip()
    app_version = (app_version or "").strip()

    if provider not in PushProvider.values:
        raise ValueError("Provider push non supporté.")
    if platform not in PushPlatform.values:
        raise ValueError("Plateforme push non supportée.")
    if not installation_id or len(installation_id) > 128:
        raise ValueError("installation_id invalide.")
    if not token:
        raise ValueError("Token push vide.")

    digest = _token_hash(token)
    rows = list(
        PushEndpoint.objects.select_for_update()
        .filter(provider=provider)
        .filter(Q(installation_id=installation_id) | Q(token_hash=digest))
        .order_by("created_at", "pk")
    )

    endpoint = rows[0] if rows else None
    for duplicate in rows[1:]:
        duplicate.delete()

    encrypted = encrypt_runtime_secret(token)
    now = timezone.now()
    values = {
        "user": user,
        "provider": provider,
        "platform": platform,
        "installation_id": installation_id,
        "token_hash": digest,
        "encrypted_token": encrypted,
        "token_hint": _token_hint(token),
        "app_version": app_version[:64],
        "active": True,
        "last_seen_at": now,
    }
    if endpoint is None:
        endpoint = PushEndpoint.objects.create(**values)
    else:
        for key, value in values.items():
            setattr(endpoint, key, value)
        endpoint.save(
            update_fields=[
                "user",
                "provider",
                "platform",
                "installation_id",
                "token_hash",
                "encrypted_token",
                "token_hint",
                "app_version",
                "active",
                "last_seen_at",
                "updated_at",
            ]
        )
    return endpoint


def revoke_push_endpoint(*, user, installation_id: str, provider: str = PushProvider.FCM) -> int:
    installation_id = (installation_id or "").strip()
    if not installation_id:
        return 0
    return PushEndpoint.objects.filter(
        user=user,
        provider=provider,
        installation_id=installation_id,
        active=True,
    ).update(active=False, updated_at=timezone.now())


def active_push_endpoints_for(user):
    return PushEndpoint.objects.filter(user=user, active=True).order_by("created_at", "pk")


def _firebase_app():
    if not getattr(settings, "MAKOLO_FIREBASE_PUSH_ENABLED", False):
        raise ImproperlyConfigured("MAKOLO_FIREBASE_PUSH_ENABLED est désactivé.")

    import firebase_admin
    from firebase_admin import credentials

    try:
        return firebase_admin.get_app("makolo-push")
    except ValueError:
        service_account = getattr(settings, "MAKOLO_FIREBASE_SERVICE_ACCOUNT_FILE", "")
        project_id = getattr(settings, "MAKOLO_FIREBASE_PROJECT_ID", "")
        options = {"projectId": project_id} if project_id else None
        if service_account:
            credential = credentials.Certificate(str(Path(service_account)))
        else:
            credential = credentials.ApplicationDefault()
        return firebase_admin.initialize_app(
            credential,
            options=options,
            name="makolo-push",
        )


def send_push_notification(*, endpoint: PushEndpoint, notification) -> str:
    from firebase_admin import messaging

    token = decrypt_runtime_secret(endpoint.encrypted_token)
    navigation = build_notification_navigation(notification)
    data = {
        "notification_id": str(notification.pk),
        "kind": str(notification.kind),
    }
    if navigation:
        data["destination"] = json.dumps(
            navigation,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    include_content = getattr(settings, "MAKOLO_PUSH_INCLUDE_MESSAGE_CONTENT", False)
    visible = messaging.Notification(
        title=notification.title if include_content else "Makolo",
        body=notification.message if include_content else "Une information vous attend dans Makolo.",
    )
    message = messaging.Message(
        token=token,
        notification=visible,
        data=data,
    )
    try:
        reference = messaging.send(message, app=_firebase_app())
    except messaging.UnregisteredError:
        PushEndpoint.objects.filter(pk=endpoint.pk).update(
            active=False,
            updated_at=timezone.now(),
        )
        raise
    return reference

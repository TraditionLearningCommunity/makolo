import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

from .models import UserDevice


DEVICE_COOKIE_NAME = "makolo_device"
DEVICE_COOKIE_MAX_AGE = 180 * 24 * 60 * 60


def _hash_device_key(raw_value):
    if not raw_value:
        return ""
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def device_key_hash_from_request(request):
    return _hash_device_key((request.COOKIES.get(DEVICE_COOKIE_NAME) or "").strip())


def _client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or None


def _device_defaults(request):
    agent = (request.META.get("HTTP_USER_AGENT") or "").strip()
    return {
        "device_name": "Navigateur Makolo",
        "device_type": "web",
        "browser": agent[:100] or None,
        "ip_address": _client_ip(request),
        "last_used": timezone.now(),
    }


def remember_account_on_device(request, response, user):
    """Remember an account without creating any authentication grant.

    The browser cookie is an opaque device identifier only. Its SHA-256 digest
    associates UserDevice rows with this browser. Authentication remains the
    normal Django session and switching account therefore requires login.
    """
    raw_key = (request.COOKIES.get(DEVICE_COOKIE_NAME) or "").strip()
    if not raw_key:
        raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_device_key(raw_key)
    UserDevice.objects.update_or_create(
        user=user,
        device_key_hash=key_hash,
        defaults=_device_defaults(request),
    )
    response.set_cookie(
        DEVICE_COOKIE_NAME,
        raw_key,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax") or "Lax",
        path="/",
    )
    return response


def remembered_accounts_for_request(request):
    key_hash = device_key_hash_from_request(request)
    current_user = getattr(request, "user", None)
    if not key_hash or not getattr(current_user, "is_authenticated", False):
        return []
    # Possessing a copied device cookie must not reveal the browser's account
    # list to an unrelated authenticated account. The current Profile must
    # already be remembered on the same browser.
    if not UserDevice.objects.filter(user=current_user, device_key_hash=key_hash).exists():
        return []
    return list(
        UserDevice.objects.filter(device_key_hash=key_hash, user__is_active=True)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )


def remembered_device_for_user(request, user_id):
    key_hash = device_key_hash_from_request(request)
    current_user = getattr(request, "user", None)
    if not key_hash or not getattr(current_user, "is_authenticated", False):
        return None
    if not UserDevice.objects.filter(user=current_user, device_key_hash=key_hash).exists():
        return None
    return (
        UserDevice.objects.select_related("user")
        .filter(device_key_hash=key_hash, user_id=user_id, user__is_active=True)
        .first()
    )


def forget_account_on_device(request, user_id):
    device = remembered_device_for_user(request, user_id)
    if device is None:
        return False
    device.delete()
    return True

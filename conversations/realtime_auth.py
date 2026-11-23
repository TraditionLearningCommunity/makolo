"""Single-use Redis tickets; credentials never belong in socket URLs or logs."""
import hashlib
import json
import secrets
import time
from functools import lru_cache
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from redis import Redis


def redis_client():
    return _client(settings.CONVERSATIONS_REDIS_URL)


@lru_cache(maxsize=4)
def _client(url):
    return Redis.from_url(url, socket_connect_timeout=1,
                          socket_timeout=1, decode_responses=True)


def key(kind, identifier):
    return f"{settings.CONVERSATIONS_REDIS_PREFIX}:{kind}:{identifier}"


def ticket_key(ticket):
    return key("ticket", hashlib.sha256(ticket.encode()).hexdigest())


def issue_ticket(request):
    ticket = secrets.token_urlsafe(32)
    expires = int(time.time()) + 900
    session = getattr(request, "session", None)
    session_key = session.session_key if session else None
    if session_key:
        expires = min(expires, int(session.get_expiry_date().timestamp()))
    auth = getattr(request, "auth", None)
    if auth is not None and hasattr(auth, "get"):
        expires = min(expires, int(auth.get("exp", expires)))
    binding = {"profile_id": str(request.user.pk), "session_key": session_key, "expires": expires}
    redis_client().set(ticket_key(ticket), json.dumps(binding), ex=60, nx=True)
    return ticket


def consume_ticket(ticket):
    if not isinstance(ticket, str) or not 32 <= len(ticket) <= 128:
        return None
    value = redis_client().getdel(ticket_key(ticket))
    return json.loads(value) if value else None


def bound_actor(binding):
    if not binding or binding["expires"] <= time.time():
        return None
    actor = get_user_model().objects.filter(pk=binding["profile_id"], is_active=True).first()
    if actor is None:
        return None
    if binding.get("session_key"):
        session = import_module(settings.SESSION_ENGINE).SessionStore(binding["session_key"])
        if str(session.get("_auth_user_id")) != str(actor.pk):
            return None
        if not constant_time_compare(session.get("_auth_user_hash", ""), actor.get_session_auth_hash()):
            return None
    return actor

"""Ephemeral state, never a global last-seen record."""
from .realtime_auth import key, redis_client


def mark_active(point_id, profile_id, *, typing=False):
    ttl = 5 if typing else 60
    redis_client().set(key("typing" if typing else "presence", f"{point_id}:{profile_id}"), "1", ex=ttl)
    return ttl

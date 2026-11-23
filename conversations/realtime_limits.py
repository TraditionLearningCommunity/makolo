"""Shared atomic, expiring budgets; fail closed when Redis is unavailable."""
from .realtime_auth import key, redis_client


def within_budget(scope, identifier, *, maximum, seconds):
    count = redis_client().eval(
        "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
        1, key(scope, identifier), seconds,
    )
    return count <= maximum

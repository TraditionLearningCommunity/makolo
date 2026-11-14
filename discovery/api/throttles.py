"""Bound repeated, user-invoked paid provider actions by authenticated Profile.

These are defense-in-depth limits shared by Django Web and DRF entry points.
They rely on the configured Django cache (use a shared cache in deployment).
"""
from rest_framework.throttling import UserRateThrottle


class _FixedUserThrottle(UserRateThrottle):
    rate = None

    def get_rate(self):
        return self.rate


class DiscoveryClarifyThrottle(_FixedUserThrottle):
    scope = "discovery_clarify"
    rate = "12/hour"


class DiscoveryResearchThrottle(_FixedUserThrottle):
    scope = "discovery_research"
    rate = "12/hour"

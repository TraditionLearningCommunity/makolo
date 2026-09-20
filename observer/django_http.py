from __future__ import annotations

from django.utils import timezone

from .adapters.http_transport import (
    PinnedStdlibHttpTransport,
    SystemHttpResolver,
)
from .django_app.models import Observation
from .django_http_state import (
    cache_robots,
    defer_host_until,
    get_cached_robots,
    release_host_lease,
    renew_host_lease,
    reserve_host_request,
)
from .errors import ObserverStateConflictError
from .http_acquisition import DirectHttpAcquisition
from .http_contracts import (
    HttpAcquisitionPolicy,
    HttpObservationContext,
)


class DjangoHttpScopeState:
    def reserve(
        self,
        hostname,
        *,
        now,
        min_interval_seconds,
        lease_seconds,
    ):
        return reserve_host_request(
            hostname,
            now=now,
            min_interval_seconds=min_interval_seconds,
            lease_seconds=lease_seconds,
        )

    def renew(self, lease, *, lease_seconds, now):
        return renew_host_lease(
            lease,
            lease_seconds=lease_seconds,
            now=now,
        )

    def release(self, lease):
        return release_host_lease(lease)

    def defer(self, hostname, *, not_before):
        return defer_host_until(
            hostname,
            not_before=not_before,
        )

    def get_robots(self, hostname, *, now):
        return get_cached_robots(hostname, now=now)

    def cache_robots(
        self,
        hostname,
        *,
        status,
        body,
        checked_at,
        expires_at,
    ):
        return cache_robots(
            hostname,
            status=status,
            body=body,
            checked_at=checked_at,
            expires_at=expires_at,
        )


class DjangoHttpContextSource:
    def get_context(self, claim) -> HttpObservationContext:
        try:
            observation = (
                Observation.objects.select_related("series")
                .get(observation_ref=claim.observation_ref)
            )
        except Observation.DoesNotExist as exc:
            raise ObserverStateConflictError(
                "claimed Observation no longer exists"
            ) from exc
        if (
            str(observation.claim_token) != claim.claim_token
            or observation.claimed_by != claim.worker_id
        ):
            raise ObserverStateConflictError(
                "claimed Observation is no longer current"
            )
        series = observation.series
        return HttpObservationContext(
            etag=series.http_etag or None,
            last_modified=series.http_last_modified or None,
            validator_artifact_ref=(
                series.validator_artifact_ref or None
            ),
        )


def build_direct_http_acquisition(
    *,
    policy: HttpAcquisitionPolicy,
    resolver=None,
    transport=None,
    scope_state=None,
    context_source=None,
    clock=None,
) -> DirectHttpAcquisition:
    return DirectHttpAcquisition(
        policy=policy,
        resolver=resolver or SystemHttpResolver(),
        transport=transport or PinnedStdlibHttpTransport(),
        scope_state=scope_state or DjangoHttpScopeState(),
        context_source=context_source or DjangoHttpContextSource(),
        clock=clock or timezone.now,
    )

from __future__ import annotations

from django.utils import timezone

from .adaptive_acquisition import AdaptiveObservationPlan
from .adaptive_contracts import AdaptiveAcquisitionPolicy
from .django_browser import build_browser_render_acquisition
from .django_http import build_direct_http_acquisition
from .http_contracts import HttpObservationContext


class _AdaptiveHttpContextSource:
    """Adaptive probes intentionally avoid conditional 304 revalidation.

    A stable HTTP shell does not prove the rendered DOM is stable because
    Browser-visible API/script responses may have changed independently.
    """

    def get_context(self, claim) -> HttpObservationContext:
        return HttpObservationContext()


def build_adaptive_observation_plan(
    *,
    policy: AdaptiveAcquisitionPolicy,
    resolver=None,
    transport=None,
    scope_state=None,
    clock=None,
    sleeper=None,
    renderer=None,
) -> AdaptiveObservationPlan:
    clock = clock or timezone.now
    http_acquisition = build_direct_http_acquisition(
        policy=policy.http_policy,
        resolver=resolver,
        transport=transport,
        scope_state=scope_state,
        context_source=_AdaptiveHttpContextSource(),
        clock=clock,
        sleeper=sleeper,
    )
    browser_acquisition = build_browser_render_acquisition(
        policy=policy.browser_policy,
        resolver=resolver,
        transport=transport,
        scope_state=scope_state,
        clock=clock,
        sleeper=sleeper,
        renderer=renderer,
    )
    return AdaptiveObservationPlan(
        policy=policy,
        http_acquisition=http_acquisition,
        browser_acquisition=browser_acquisition,
    )

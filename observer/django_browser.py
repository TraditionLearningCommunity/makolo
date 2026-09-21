from __future__ import annotations

from django.utils import timezone

from .adapters.playwright_browser import PlaywrightBrowserRenderer
from .browser_acquisition import BrowserRenderAcquisition
from .browser_contracts import BrowserAcquisitionPolicy
from .django_http import build_direct_http_acquisition


def build_browser_render_acquisition(
    *,
    policy: BrowserAcquisitionPolicy,
    resolver=None,
    transport=None,
    scope_state=None,
    clock=None,
    sleeper=None,
    renderer=None,
) -> BrowserRenderAcquisition:
    clock = clock or timezone.now
    http_acquisition = build_direct_http_acquisition(
        policy=policy.http_policy,
        resolver=resolver,
        transport=transport,
        scope_state=scope_state,
        clock=clock,
        sleeper=sleeper,
    )
    return BrowserRenderAcquisition(
        policy=policy,
        http_acquisition=http_acquisition,
        renderer=renderer or PlaywrightBrowserRenderer(),
        clock=clock,
    )

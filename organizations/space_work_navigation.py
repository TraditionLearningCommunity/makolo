"""Presentation-only MT7 Work return context.

No permission is conveyed by a page, section or URL. Every destination must
re-read its own owner under the viewer's current Space responsibility.
"""
from urllib.parse import urlencode

from django.http import Http404
from django.urls import reverse


WORK_SECTIONS = frozenset({
    "preparation", "upcoming", "active", "blocked", "completed",
    "activities", "offers", "routes", "vehicles", "requests",
})
MAX_WORK_PAGE = 834


def work_page_number(raw, *, required=False):
    """Return a bounded 1-based page; absent means root, not page zero."""
    if raw is None or raw == "":
        if required:
            return 1
        return None
    if not isinstance(raw, str) or not raw.isdecimal() or len(raw) > 4:
        raise Http404
    page = int(raw)
    if not 1 <= page <= MAX_WORK_PAGE:
        raise Http404
    return page


def work_back_url(*, space, responsibility, section, origin_page=None):
    """Root anchor or a specific authorized Work collection page."""
    if section not in WORK_SECTIONS:
        section = "activities"
    if origin_page is not None:
        return (
            reverse(
                "organizations:space-work-collection",
                kwargs={"slug": space.slug, "section": section},
            ) + "?" + urlencode({
                "responsibility": responsibility,
                "page": origin_page,
            })
        )
    return (
        reverse("organizations:space-work", kwargs={"slug": space.slug})
        + "?" + urlencode({"responsibility": responsibility})
        + f"#work-{section}"
    )

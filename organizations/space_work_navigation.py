"""Presentation-only MT7 Work return context.

No permission is conveyed by a page, section or URL. Every destination must
re-read its own owner under the viewer's current Space responsibility.
"""
from urllib.parse import urlencode, urlsplit, urlunsplit

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


_LINK_FIELDS = frozenset({
    "url", "parent_url", "back_url", "next_page_url",
    "previous_page_url", "next", "previous", "next_occurrences",
    "previous_occurrences", "next_work", "previous_work",
})


def _origin_url(url, origin_page):
    """Append an origin only to our own Work N2 URLs."""
    if not isinstance(url, str) or not url.startswith("/"):
        return url
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or "/work/" not in parsed.path:
        return url
    if "work_origin_page=" in parsed.query:
        return url
    query = parsed.query
    query += ("&" if query else "") + urlencode({"work_origin_page": origin_page})
    return urlunsplit(("", "", parsed.path, query, parsed.fragment))


def restore_work_origin(*, request, context, context_key, space,
                        responsibility, section):
    """Preserve N1 collection across N2 relations, children and pagination.

    A user-controlled page is a navigation hint only. The selected domain owner
    and every action continue to be authorized independently.
    """
    origin_page = work_page_number(request.GET.get("work_origin_page"))
    if origin_page is None:
        return

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            return {
                key: (
                    _origin_url(item, origin_page)
                    if key in _LINK_FIELDS else rewrite(item)
                )
                for key, item in value.items()
            }
        return value

    data = context.get(context_key)
    if not isinstance(data, dict):
        return
    original_back = data.get("back_url") or ""
    updated = rewrite(data)
    root_path = reverse("organizations:space-work", kwargs={"slug": space.slug})
    if urlsplit(original_back).path == root_path:
        updated["back_url"] = work_back_url(
            space=space, responsibility=responsibility, section=section,
            origin_page=origin_page,
        )
    context[context_key] = updated

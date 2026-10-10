"""Read-only grouping and return-address composition for retrieval UX.

This presentation helper never searches owners or changes permissions. It
groups only the already authorized rows provided by owner selectors.
"""
from collections import OrderedDict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _with_return_context(url, context):
    if not url or not url.startswith("/") or url.startswith("//"):
        return None
    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.update({
        key: str(value)
        for key, value in context.items()
        if value not in (None, "")
    })
    return urlunsplit(("", "", parsed.path, urlencode(params), parsed.fragment))


def group_retrieval_rows(items, *, history=False, context=None):
    """Keep source ranking within each human-type group, without a new score."""
    context = context or {}
    groups = OrderedDict()
    for item in items:
        owner = item.get("source") or {}
        kind = str(owner.get("kind") or "")
        source_id = str(owner.get("id") or "")
        if not kind or not source_id:
            continue
        outcome = item.get("outcome") or {}
        title = (
            outcome.get("label") or "Expériences passées"
            if history else item.get("human_type") or "Autres résultats"
        )
        key = f"{kind}:{source_id}"
        result = dict(item)
        result["anchor"] = f"result-{kind}-{source_id}"
        result["selection_key"] = key
        owner_href = (
            (item.get("links") or {}).get("detail") if history
            else item.get("destination")
        )
        result["web_destination"] = _with_return_context(
            owner_href, {**context, "selected": key},
        )
        if title not in groups:
            groups[title] = {"label": title, "items": []}
        groups[title]["items"].append(result)
    return list(groups.values())

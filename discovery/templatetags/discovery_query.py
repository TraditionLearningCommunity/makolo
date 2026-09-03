from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag
def discovery_without(intent, key):
    """Build a canonical Discover query without one applied constraint.

    The query is rebuilt from the resolved DiscoveryIntent rather than the raw
    natural-language request so removing an interpreted constraint does not
    immediately re-introduce it through re-interpretation. A bounded technical
    marker lets beta telemetry count corrections without storing query text.
    """

    params = dict(intent.to_search_params())
    if key == "nearby":
        for item in ("lat", "lon", "radius_km", "ordering"):
            params.pop(item, None)
    else:
        params.pop(key, None)
    if key in {"vertical", "place", "when", "period", "price", "nearby"}:
        params["_correction"] = key
    return urlencode(params)

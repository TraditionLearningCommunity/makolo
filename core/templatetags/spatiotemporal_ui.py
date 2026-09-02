from __future__ import annotations

from django import template
from django.utils import timezone

from spatiotemporal.context import get_journey_spatiotemporal_context
from spatiotemporal.spatial import get_spatial_context
from spatiotemporal.temporal import get_temporal_context


register = template.Library()


def _relative_label(delta):
    seconds = round(delta.total_seconds())
    if seconds <= 0:
        return "Maintenant"
    minutes = max(1, seconds // 60)
    if minutes < 60:
        return f"Dans {minutes} min"
    hours, remaining = divmod(minutes, 60)
    if hours < 24:
        return f"Dans {hours} h" + (f" {remaining:02d}" if remaining else "")
    days = hours // 24
    return f"Dans {days} j"


@register.simple_tag
def occurrence_temporal_label(occurrence):
    if occurrence is None:
        return ""
    temporal = get_temporal_context(occurrence)
    if temporal.state.value == "cancelled":
        return "Annulée"
    if temporal.state.value == "active":
        return "En cours"
    if temporal.state.value == "ended":
        return "Terminée"
    return _relative_label(temporal.starts_in)


@register.inclusion_tag("core/_spatiotemporal_context.html", takes_context=True)
def journey_spatiotemporal(context, journey):
    request = context.get("request")
    viewer = getattr(request, "user", None)
    if viewer is None or not getattr(viewer, "is_authenticated", False) or journey.beneficiary_id != viewer.pk:
        return {"m6": None}
    return {"m6": get_journey_spatiotemporal_context(journey, now=timezone.now()), "private": True}


@register.inclusion_tag("core/_spatiotemporal_context.html")
def occurrence_spatiotemporal(occurrence):
    if occurrence is None:
        return {"m6": None}
    temporal = get_temporal_context(occurrence)
    spatial = get_spatial_context(occurrence)
    return {
        "m6": {
            "occurrence": occurrence,
            "temporal": temporal,
            "spatial": spatial,
            "mobility": None,
            "hazards": (),
            "advices": (),
        },
        "private": False,
    }

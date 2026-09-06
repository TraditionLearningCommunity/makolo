from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from .card_contract import RepresentationPresentation


def _related(obj, name):
    try:
        return getattr(obj, name)
    except (AttributeError, ObjectDoesNotExist):
        return None


def _event_representation(activity) -> RepresentationPresentation | None:
    event = _related(activity, "event_vertical")
    if event is None:
        return None
    image = getattr(event, "cover_image", None)
    category = getattr(event, "category", None)
    eyebrow = getattr(category, "name", None) if category is not None else None
    return RepresentationPresentation(
        kind="image" if image else "identity",
        image_url=image.url if image else None,
        eyebrow=eyebrow,
    )


def _transport_representation(activity, occurrence=None) -> RepresentationPresentation | None:
    service = _related(activity, "transport_service")
    departure = _related(occurrence, "transport_departure") if occurrence is not None else None
    if service is None and departure is None:
        return None
    route = getattr(service, "route", None) if service is not None else None
    route_label = None
    if route is not None:
        origin = getattr(route, "origin", None)
        destination = getattr(route, "destination", None)
        if origin is not None and destination is not None:
            origin_label = getattr(origin, "locality", None) or getattr(origin, "name", "")
            destination_label = getattr(destination, "locality", None) or getattr(destination, "name", "")
            if origin_label and destination_label:
                route_label = f"{origin_label} → {destination_label}"
    return RepresentationPresentation(
        kind="route",
        eyebrow=route_label or "Départ",
        route_label=route_label,
    )


def _service_representation(activity) -> RepresentationPresentation | None:
    service = _related(activity, "service_details")
    if service is None:
        return None
    get_label = getattr(service, "get_service_kind_display", None)
    eyebrow = get_label() if callable(get_label) else None
    return RepresentationPresentation(kind="service", eyebrow=eyebrow)


def resolve_activity_representation(*, activity, occurrence=None) -> RepresentationPresentation:
    """Resolve a public presentation without making a vertical own generic media.

    Activity is the canonical subject. Contextual verticals may contribute facts
    such as Event.cover_image or a Transport route, while the generic fallback
    remains valid with no image and no fabricated media.
    """

    for resolver in (_transport_representation,):
        representation = resolver(activity, occurrence)
        if representation is not None:
            return representation
    for resolver in (_event_representation, _service_representation):
        representation = resolver(activity)
        if representation is not None:
            return representation
    return RepresentationPresentation(kind="identity")


def resolve_opportunity_representation(*, state_label: str | None = None) -> RepresentationPresentation:
    """Keep direct Opportunity candidates distinct from Activity/Occurrence."""

    return RepresentationPresentation(kind="opportunity", eyebrow=state_label)

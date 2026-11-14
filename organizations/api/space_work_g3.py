"""MT5 — owner-backed Commerce and Transport depths.

Only call after Work has selected an owner within the current authorized
Space/responsibility. Read models, not copies of Commerce/Transport truth.
"""
from uuid import UUID

from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from commerce.models import CommerceOrder, Offer
from transport.models import TransportDeparture, TransportRoute, TransportService, Vehicle


LIMIT = 12


def _uuid(raw):
    try:
        return UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        return None


def _page(qs, *, offset, serialize):
    rows = list(qs[offset:offset + LIMIT + 1])
    return {
        "items": [serialize(row) for row in rows[:LIMIT]],
        "offset": offset,
        "limit": LIMIT,
        "has_more": len(rows) > LIMIT,
        "coverage_state": "partial" if offset or len(rows) > LIMIT else "established",
    }


def _occurrence_row(occurrence):
    from .space_work_projection import g1_occurrence_is_selectable

    return {
        "source": {"kind": "occurrence", "id": str(occurrence.pk)},
        "title": occurrence.label or occurrence.activity.title,
        "state": occurrence.status,
        "timing": {
            "start_date": occurrence.start_date,
            "start_time": occurrence.start_time,
            "timezone": occurrence.timezone,
        },
        "openable": g1_occurrence_is_selectable(occurrence),
    }


def _activity_row(activity):
    return {
        "source": {"kind": "activity", "id": str(activity.pk)},
        "title": activity.title,
        "state": activity.status,
        "openable": True,
    }


def _departure_qs(space, visible_ids):
    return (
        Occurrence.objects.filter(
            activity__space=space,
            activity_id__in=visible_ids,
            transport_departure__isnull=False,
        )
        .select_related("activity", "transport_departure")
        .order_by("start_date", "start_time", "pk")
    )


def g3_owner_depth(*, space, selection, profile, visible_ids,
                   operations_ids, offset=0, secondary_offset=0):
    """Returns a minimum-disclosure projection for one already-selected owner."""
    if space.archetype not in {"commerce", "transport_operator"}:
        return None
    source = selection.get("source") or {}
    kind, owner_id = source.get("kind"), _uuid(source.get("id"))
    if owner_id is None:
        return None

    if space.archetype == "commerce":
        if kind == "activity":
            activity = Activity.objects.filter(
                pk=owner_id, space=space, pk__in=visible_ids,
            ).first()
            if activity is None:
                return None
            offers = Offer.objects.filter(
                activity=activity,
            ).order_by("name", "pk")
            return {
                "kind": "commerce_activity",
                "facts": {
                    "can_manage_offer": can(
                        profile, PermissionCode.ACTIVITY_COMMERCE_MANAGE,
                        activity=activity,
                    ),
                },
                "offers": _page(
                    offers, offset=offset,
                    serialize=lambda offer: {
                        "source": {"kind": "offer", "id": str(offer.pk)},
                        "title": offer.name,
                        "state": offer.status, "openable": True,
                    },
                ),
            }
        if kind == "offer":
            offer = (
                Offer.objects.filter(
                    pk=owner_id, activity__space=space,
                    activity_id__in=visible_ids,
                )
                .select_related("activity", "occurrence", "capacity_pool")
                .prefetch_related("payment_options")
                .first()
            )
            if offer is None:
                return None
            return {
                "kind": "offer",
                "facts": {
                    "unit_price": str(offer.unit_price),
                    "currency": offer.currency,
                    "payment_mode": offer.payment_mode,
                    "payment_modes": offer.allowed_payment_modes,
                    "min_quantity": offer.min_quantity,
                    "max_quantity": offer.max_quantity,
                    "available_from": offer.available_from,
                    "available_until": offer.available_until,
                    "currently_available": offer.is_currently_available,
                    "can_manage_offer": can(
                        profile, PermissionCode.ACTIVITY_COMMERCE_MANAGE,
                        activity=offer.activity,
                    ),
                    "capacity_pool_bound": bool(offer.capacity_pool_id),
                    "occurrence": (
                        {"kind": "occurrence", "id": str(offer.occurrence_id)}
                        if offer.occurrence_id else None
                    ),
                },
            }
        if kind == "commerce_order":
            order = (
                CommerceOrder.objects.filter(
                    pk=owner_id, payee_space=space,
                    journey__activity_id__in=visible_ids,
                ).select_related("journey__activity").first()
            )
            if order is None:
                return None

            def serialize_line(item):
                return {
                    "id": str(item.pk),
                    "label": item.label_snapshot,
                    "quantity": item.quantity,
                    "unit_price": str(item.unit_price),
                    "line_total": str(item.line_total),
                    "currency": order.currency,
                }

            return {
                "kind": "commerce_order",
                "facts": {
                    "reference": order.reference,
                    "currency": order.currency,
                    "payment_mode": order.payment_mode,
                    "subtotal": str(order.subtotal),
                    "discount_total": str(order.discount_total),
                    "total": str(order.total),
                    "confirmed_at": order.confirmed_at,
                    "expires_at": order.expires_at,
                    # An Order does not own Payment success or fulfilment.
                    "payment_state": "not_projected",
                    "delivery_state": "not_projected",
                },
                "lines": _page(
                    order.items.order_by("created_at", "pk"),
                    offset=offset, serialize=serialize_line,
                ),
            }
        return None

    # Structural TransportRoute and Vehicle are Space-wide reads. The Work
    # owner selector already requires direct portfolio permission for these.
    if kind == "transport_route":
        route = (
            TransportRoute.objects.filter(pk=owner_id, space=space)
            .prefetch_related("stops__place").first()
        )
        if route is None:
            return None
        services = TransportService.objects.filter(
            route=route, activity_id__in=visible_ids,
        ).select_related("activity").order_by("activity__title", "pk")
        return {
            "kind": "transport_route",
            "facts": {"code": route.code or None, "active": route.active},
            "services": _page(
                services, offset=offset,
                serialize=lambda svc: _activity_row(svc.activity),
            ),
            "departures": _page(
                _departure_qs(space, visible_ids).filter(
                    activity__transport_service__route=route,
                ),
                offset=secondary_offset, serialize=_occurrence_row,
            ),
        }
    if kind == "vehicle":
        vehicle = Vehicle.objects.filter(pk=owner_id, space=space).first()
        if vehicle is None:
            return None
        return {
            "kind": "vehicle",
            "facts": {
                "vehicle_type": vehicle.vehicle_type,
                "passenger_capacity": vehicle.passenger_capacity,
                "active": vehicle.active,
                # Vehicle identification belongs to the Space operator.
                "registration": (
                    vehicle.registration or None
                    if has_direct_space_permission(
                        profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE,
                    ) else None
                ),
            },
            "departures": _page(
                _departure_qs(space, visible_ids).filter(
                    transport_departure__vehicle=vehicle,
                ),
                offset=offset, serialize=_occurrence_row,
            ),
        }
    if kind == "activity":
        service = TransportService.objects.filter(
            activity_id=owner_id, activity__space=space,
            activity_id__in=visible_ids,
        ).select_related("route").first()
        if service is None:
            return None
        return {
            "kind": "transport_service",
            "facts": {
                "route": {
                    "kind": "transport_route", "id": str(service.route_id),
                    "name": service.route.name,
                },
                "mode": service.mode,
            },
            "departures": _page(
                _departure_qs(space, visible_ids).filter(activity_id=owner_id),
                offset=offset, serialize=_occurrence_row,
            ),
        }
    if kind == "occurrence":
        occurrence = (
            Occurrence.objects.filter(
                pk=owner_id, activity__space=space,
                activity_id__in=visible_ids,
                transport_departure__isnull=False,
            ).select_related(
                "activity__transport_service__route",
                "transport_departure__vehicle",
                "transport_departure__passenger_capacity_pool",
            ).first()
        )
        if occurrence is None:
            return None
        departure = occurrence.transport_departure
        service = occurrence.activity.transport_service
        authorized_ops = occurrence.activity_id in operations_ids
        authorized_manage = can(
            profile, PermissionCode.ACTIVITY_OPERATIONS_MANAGE,
            activity=occurrence.activity,
        )
        return {
            "kind": "transport_departure",
            "facts": {
                "departure_id": str(departure.pk),
                "route": {
                    "kind": "transport_route",
                    "id": str(service.route_id),
                    "name": service.route.name,
                },
                "vehicle": (
                    {
                        "kind": "vehicle", "id": str(departure.vehicle_id),
                        "label": departure.vehicle.label,
                        "physical_capacity": departure.vehicle.passenger_capacity,
                    }
                    if authorized_ops and departure.vehicle_id else None
                ),
                "vehicle_assignment_known": authorized_ops,
                "operational_reference": (
                    departure.operational_reference or None
                    if authorized_ops else None
                ),
                "boarding_instructions": (
                    departure.boarding_instructions or None
                    if authorized_ops else None
                ),
                # Capacity remains with CapacityPool; presentation uses
                # the already authorized Work context availability snapshot.
                "capacity_basis": "capacity_pool",
                "operations_visible": authorized_ops,
                "can_manage_operations": authorized_manage,
            },
        }
    return None

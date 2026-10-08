from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import (
    activity_ids_with_direct_permission,
    current_mandates,
    has_direct_space_permission,
)
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer, OfferStatus
from journeys.collaboration_models import JourneyBlockerStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.space_product import operating_preset_for_space, operational_footprint_for_space
from services.selectors import service_journeys_visible_to
from transport.models import TransportRoute, Vehicle


PREVIEW_LIMIT = 20


def _space_has_activity_portfolio_access(profile, space):
    return (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE)
    )


def _mandated_activity_ids(profile, space):
    return set(
        current_mandates()
        .filter(
            profile=profile,
            scope_type=AuthorityScope.ACTIVITY,
            activity__space=space,
        )
        .exclude(activity_id=None)
        .values_list("activity_id", flat=True)
    )


def _visible_activity_ids(profile, space):
    if _space_has_activity_portfolio_access(profile, space):
        return set(space.activities.values_list("pk", flat=True))
    return _mandated_activity_ids(profile, space)


def _activity_capability_sets(profile):
    return {
        "manage": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_MANAGE)),
        "operations": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_OPERATIONS_VIEW)),
        "commerce": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_COMMERCE_VIEW)),
        "requests": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)),
        "service_cases": set(
            activity_ids_with_direct_permission(
                profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL
            )
        )
        | set(
            activity_ids_with_direct_permission(
                profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED
            )
        ),
    }


def _capabilities_for_activity(activity_id, caps):
    result = ["view"]
    if activity_id in caps["manage"]:
        result.append("manage")
    if activity_id in caps["operations"]:
        result.append("open_operations")
    if activity_id in caps["commerce"]:
        result.append("open_commerce")
    if activity_id in caps["requests"]:
        result.append("open_requests")
    if activity_id in caps["service_cases"]:
        result.append("open_service_cases")
    return result


def _activity_item(activity, caps):
    return {
        "key": f"activity:{activity.pk}",
        "source": {"kind": "activity", "id": str(activity.pk)},
        "kind": "activity",
        "title": activity.title,
        "summary": activity.short_description or None,
        "timing": {},
        "state": activity.status,
        "context": {},
        "links": {"detail": f"/api/v1/activities/{activity.pk}/"},
        "capabilities": _capabilities_for_activity(activity.pk, caps),
    }


def _occurrence_item(occurrence, caps):
    is_departure = hasattr(occurrence, "transport_departure")
    operation_visible = occurrence.activity_id in caps["operations"]
    current_day_of = operation_visible and occurrence.is_ongoing
    links = {
        "detail": f"/api/v1/occurrences/{occurrence.pk}/",
        "activity": f"/api/v1/activities/{occurrence.activity_id}/",
    }
    capabilities = _capabilities_for_activity(occurrence.activity_id, caps)
    if current_day_of:
        links.update(
            {
                "day_of": f"/api/v1/operations/occurrences/{occurrence.pk}/day-of/",
                "live": f"/api/v1/operations/occurrences/{occurrence.pk}/live/",
            }
        )
        capabilities.append("open_day_of")
    return {
        "key": f"occurrence:{occurrence.pk}",
        "source": {"kind": "occurrence", "id": str(occurrence.pk)},
        "kind": "departure" if is_departure else "occurrence",
        "title": occurrence.label or occurrence.activity.title,
        "summary": occurrence.activity.short_description or None,
        "timing": {
            "kind": occurrence.timing_kind,
            "start_date": occurrence.start_date,
            "start_time": occurrence.start_time,
            "end_date": occurrence.end_date,
            "end_time": occurrence.end_time,
            "timezone": occurrence.timezone,
        },
        "state": occurrence.status,
        "context": {
            "activity": {
                "id": str(occurrence.activity_id),
                "title": occurrence.activity.title,
            }
        },
        "links": links,
        "capabilities": capabilities,
    }


def _offer_item(offer, caps):
    return {
        "key": f"offer:{offer.pk}",
        "source": {"kind": "offer", "id": str(offer.pk)},
        "kind": "offer",
        "title": offer.name,
        "summary": offer.description or None,
        "timing": {
            "available_from": offer.available_from,
            "available_until": offer.available_until,
        },
        "state": offer.status,
        "context": {
            "activity": {
                "id": str(offer.activity_id),
                "title": offer.activity.title,
            }
        },
        "links": {"activity": f"/api/v1/activities/{offer.activity_id}/"},
        "capabilities": _capabilities_for_activity(offer.activity_id, caps),
    }


def _journey_item(journey, caps):
    item = {
        "key": f"journey:{journey.pk}",
        "source": {"kind": "journey", "id": str(journey.pk)},
        "kind": "service_case" if journey.workflow == WorkflowKind.SERVICE else "journey",
        "title": journey.activity.title,
        "summary": None,
        "timing": {
            "expires_at": journey.expires_at,
            "started_at": journey.started_at,
            "fulfilled_at": journey.fulfilled_at,
        },
        "state": journey.status,
        "context": {
            "activity": {
                "id": str(journey.activity_id),
                "title": journey.activity.title,
            },
            "workflow": journey.workflow,
        },
        "links": {"activity": f"/api/v1/activities/{journey.activity_id}/"},
        "capabilities": _capabilities_for_activity(journey.activity_id, caps),
    }
    # A continuity facet is present only because this owner is a real,
    # progressive journey.  It is not a transversal Business Entry state.
    item["continuity_facet"] = {
        "identity": f"journey:{journey.pk}",
        "blockers": [
            {"source": "journey_blocker", "id": str(blocker.pk)}
            for blocker in journey.blockers.all()
            if blocker.status == JourneyBlockerStatus.ACTIVE
        ],
        "next": [] if journey.status in {
            JourneyStatus.FULFILLED,
            JourneyStatus.REJECTED,
            JourneyStatus.CANCELLED,
            JourneyStatus.EXPIRED,
        } else ["owner_transition"],
    }
    return item


def _order_item(order, caps):
    return {
        "key": f"commerce_order:{order.pk}",
        "source": {"kind": "commerce_order", "id": str(order.pk)},
        "kind": "order",
        "title": order.reference,
        "summary": None,
        "timing": {
            "expires_at": order.expires_at,
            "confirmed_at": order.confirmed_at,
        },
        "state": order.status,
        "context": {
            "activity": {
                "id": str(order.journey.activity_id),
                "title": order.journey.activity.title,
            }
        },
        "links": {"activity": f"/api/v1/activities/{order.journey.activity_id}/"},
        "capabilities": _capabilities_for_activity(order.journey.activity_id, caps),
    }


def _route_item(route):
    return {
        "key": f"transport_route:{route.pk}",
        "source": {"kind": "transport_route", "id": str(route.pk)},
        "kind": "route",
        "title": route.name,
        "summary": None,
        "timing": {},
        "state": "active" if route.active else "inactive",
        "context": {},
        "links": {},
        "capabilities": ["view"],
    }


def _vehicle_item(vehicle):
    return {
        "key": f"vehicle:{vehicle.pk}",
        "source": {"kind": "vehicle", "id": str(vehicle.pk)},
        "kind": "vehicle",
        "title": vehicle.label,
        "summary": None,
        "timing": {},
        "state": "active" if vehicle.active else "inactive",
        "context": {"passenger_capacity": vehicle.passenger_capacity},
        "links": {},
        "capabilities": ["view"],
    }


def _empty_section(*, identity, role, representation):
    return {
        "identity": identity,
        "representation": representation,
        "role": role,
        "coverage_state": "established",
        "items": [],
        "has_more": False,
        "links": {},
    }


def _empty_sections(*, activity_representation, include_offers=False, include_transport=False):
    sections = {
        "preparation": _empty_section(identity="preparation", role="continuity", representation="À préparer"),
        "upcoming": _empty_section(identity="upcoming", role="continuity", representation="À venir"),
        "active": _empty_section(identity="active", role="continuity", representation="En cours"),
        "blocked": _empty_section(identity="blocked", role="continuity", representation="Bloqués"),
        "completed": _empty_section(identity="completed", role="history", representation="Terminés"),
    }
    # These are structural owner collections, deliberately separate from
    # continuity sections.  They are added only when the scoped composition
    # can establish the corresponding owner world.
    sections["activities"] = _empty_section(
        identity="activities", role="structure", representation=activity_representation
    )
    if include_offers:
        sections["offers"] = _empty_section(
            identity="offers", role="structure", representation="Offres"
        )
    if include_transport:
        sections["routes"] = _empty_section(
            identity="routes", role="structure", representation="Routes"
        )
        sections["vehicles"] = _empty_section(
            identity="vehicles", role="structure", representation="Véhicules"
        )
    return sections


def _append(section, item):
    if len(section["items"]) < PREVIEW_LIMIT:
        section["items"].append(item)
    else:
        section["has_more"] = True


def _activity_scope_from_responsibility(profile, space, responsibility_key):
    if not responsibility_key or responsibility_key == "all":
        return None
    prefix = "mandate:"
    if not responsibility_key.startswith(prefix):
        return set()
    mandate_id = responsibility_key[len(prefix) :]
    mandate = (
        current_mandates()
        .filter(profile=profile, pk=mandate_id)
        .filter(
            Q(scope_type=AuthorityScope.SPACE, space=space)
            | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=space)
        )
        .first()
    )
    if mandate is None:
        return set()
    if mandate.scope_type == AuthorityScope.ACTIVITY:
        return {mandate.activity_id}
    return None


def _journey_section(journey):
    if journey.blockers.filter(status=JourneyBlockerStatus.ACTIVE).exists():
        return "blocked"
    if journey.status in {
        JourneyStatus.DRAFT,
        JourneyStatus.SUBMITTED,
        JourneyStatus.PENDING_APPROVAL,
        JourneyStatus.PENDING_PAYMENT,
    }:
        return "preparation"
    if journey.status in {
        JourneyStatus.APPROVED,
        JourneyStatus.CONFIRMED,
        JourneyStatus.IN_PROGRESS,
    }:
        return "active"
    if journey.status in {
        JourneyStatus.FULFILLED,
        JourneyStatus.REJECTED,
        JourneyStatus.CANCELLED,
        JourneyStatus.EXPIRED,
    }:
        return "completed"
    return None


def build_space_work_projection(*, profile, space, responsibility_key=None):
    visible_ids = _visible_activity_ids(profile, space)
    lens_ids = _activity_scope_from_responsibility(
        profile, space, responsibility_key
    )
    if lens_ids == set():
        return None
    if lens_ids is not None:
        visible_ids &= lens_ids

    preset = operating_preset_for_space(space)
    caps = _activity_capability_sets(profile)
    direct_portfolio = _space_has_activity_portfolio_access(profile, space)
    transport_visible = (
        direct_portfolio
        and "transport" in operational_footprint_for_space(space).signals
    )
    commerce_visible = bool(visible_ids & caps["commerce"])
    sections = _empty_sections(
        activity_representation=preset.primary_business_label,
        include_offers=commerce_visible,
        include_transport=transport_visible,
    )
    now = timezone.now()
    today = timezone.localdate()

    activities = Activity.objects.filter(space=space, pk__in=visible_ids).order_by("title", "pk")
    for activity in activities:
        if activity.status == ActivityStatus.DRAFT:
            target = "preparation"
        elif activity.status == ActivityStatus.PUBLISHED:
            target = "activities"
        elif activity.status in {ActivityStatus.COMPLETED, ActivityStatus.CANCELLED, ActivityStatus.ARCHIVED}:
            target = "completed"
        else:
            continue
        _append(sections[target], _activity_item(activity, caps))

    occurrences = (
        Occurrence.objects.filter(activity__space=space, activity_id__in=visible_ids)
        .select_related("activity", "transport_departure")
        .order_by("start_date", "start_time", "pk")
    )
    for occurrence in occurrences:
        if occurrence.status == OccurrenceStatus.DRAFT:
            target = "preparation"
        elif occurrence.status == OccurrenceStatus.COMPLETED:
            target = "completed"
        elif occurrence.status == OccurrenceStatus.CANCELLED:
            target = "completed"
        elif occurrence.status == OccurrenceStatus.SCHEDULED and occurrence.is_ongoing:
            target = "active"
        elif occurrence.status == OccurrenceStatus.SCHEDULED and (
            (occurrence.start_at is not None and occurrence.start_at > now)
            or (occurrence.start_at is None and occurrence.start_date and occurrence.start_date > today)
        ):
            target = "upcoming"
        else:
            continue
        _append(sections[target], _occurrence_item(occurrence, caps))

    commerce_activity_ids = visible_ids & caps["commerce"]
    for offer in (
        Offer.objects.filter(activity_id__in=commerce_activity_ids)
        .select_related("activity")
        .order_by("activity_id", "name", "pk")
    ):
        if offer.status == OfferStatus.DRAFT:
            target = "preparation"
        elif offer.status == OfferStatus.ACTIVE:
            target = "offers"
        elif offer.status == OfferStatus.ARCHIVED:
            target = "completed"
        else:
            continue
        _append(sections[target], _offer_item(offer, caps))

    if has_direct_space_permission(profile, space, PermissionCode.ORDERS_VIEW):
        orders = (
            CommerceOrder.objects.filter(
                payee_space=space,
                journey__activity_id__in=visible_ids,
            )
            .select_related("journey__activity")
            .order_by("-created_at", "pk")
        )
        for order in orders:
            if order.status == CommerceOrderStatus.DRAFT:
                target = "preparation"
            elif order.status in {CommerceOrderStatus.PENDING, CommerceOrderStatus.CONFIRMED}:
                target = "active"
            elif order.status in {
                CommerceOrderStatus.CANCELLED,
                CommerceOrderStatus.EXPIRED,
                CommerceOrderStatus.REFUNDED,
            }:
                target = "completed"
            else:
                continue
            _append(sections[target], _order_item(order, caps))

    education_ids = visible_ids & caps["requests"]
    if education_ids:
        for journey in (
            Journey.objects.filter(
                activity_id__in=education_ids,
                workflow=WorkflowKind.REGISTRATION,
            )
            .select_related("activity")
            .prefetch_related("blockers")
            .order_by("-created_at", "pk")
        ):
            target = _journey_section(journey)
            if target:
                _append(sections[target], _journey_item(journey, caps))

    service_ids = visible_ids & caps["service_cases"]
    if service_ids:
        for journey in (
            service_journeys_visible_to(profile)
            .filter(activity_id__in=service_ids)
            .select_related("activity")
            .prefetch_related("blockers")
        ):
            target = _journey_section(journey)
            if target:
                _append(sections[target], _journey_item(journey, caps))

    if transport_visible:
        for route in TransportRoute.objects.filter(space=space).order_by("name", "pk"):
            _append(sections["routes"], _route_item(route))
        for vehicle in Vehicle.objects.filter(space=space).order_by("label", "pk"):
            _append(sections["vehicles"], _vehicle_item(vehicle))

    footprint = (
        list(operational_footprint_for_space(space).signals)
        if direct_portfolio
        else []
    )
    return {
        "space": {
            "id": str(space.pk),
            "slug": space.slug,
            "name": space.name,
        },
        "archetype": space.archetype,
        "primary_business_label": preset.primary_business_label,
        "authority": {
            "scope": "space" if direct_portfolio else "activity_limited",
            "limited_to_activities": not direct_portfolio,
        },
        "responsibility": responsibility_key or "all",
        "operational_footprint": {"signals": footprint},
        "composition_state": "established",
        "coverage_state": "established",
        "sections": sections,
        "links": {
            "workspace": f"/api/v1/organizations/workspaces/{space.slug}/",
        },
        "capabilities": {
            "create_activity": has_direct_space_permission(
                profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE
            ),
        },
    }

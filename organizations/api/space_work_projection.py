from __future__ import annotations

from urllib.parse import urlencode

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from activities.selectors import primary_place_for_occurrence
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import (
    activity_ids_with_direct_permission,
    current_mandates,
    has_direct_space_permission,
)
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer, OfferStatus
from journeys.collaboration_models import JourneyBlockerStatus
from journeys.models import (
    Journey, JourneyRequest, JourneyStatus, RequestStatus, WorkflowKind,
)
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL,
    CASE_SCOPE_VIEW_ASSIGNED,
    service_case_scope,
)
from organizations.space_product import (
    operating_preset_for_space, visible_operational_footprint_for_space,
)
from organizations.space_work_composition import compose_space_work_business_world
from organizations.space_work_presentation import (
    ordered_work_section_keys,
    work_presentation_for_space,
)
from requirements.contracts import RequirementAssessmentState
from services.models import ServiceRequirementAssessment
from services.selectors import service_journeys_visible_to
from operations.occurrence_live import occurrence_live_phase
from transport.models import TransportRoute, Vehicle


PREVIEW_LIMIT = 20


def _space_has_activity_portfolio_access(profile, space):
    return (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE)
    )


def _mandated_activity_ids(profile, space):
    """Only work-relevant authority may disclose Activity work details.

    Scanner, marketing or other narrow Activity Mandates are not a grant to
    read an Activity portfolio. Owner-specific read rights remain scoped to
    their actual Activity, and downstream selectors recheck sensitive rows.
    """
    work_permissions = (
        PermissionCode.ACTIVITY_VIEW,
        PermissionCode.ACTIVITY_MANAGE,
        PermissionCode.ACTIVITY_OPERATIONS_VIEW,
        PermissionCode.ACTIVITY_COMMERCE_VIEW,
        PermissionCode.ACTIVITY_REQUESTS_VIEW,
        PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
        PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
    )
    return set(
        current_mandates()
        .filter(
            profile=profile,
            scope_type=AuthorityScope.ACTIVITY,
            activity__space=space,
            role__role_permissions__permission__code__in=work_permissions,
            role__role_permissions__permission__is_active=True,
        )
        .exclude(activity_id=None)
        .values_list("activity_id", flat=True)
        .distinct()
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
    # Match the Operations owner phase: pre-arrival is already actionable.
    current_day_of = operation_visible and occurrence_live_phase(occurrence) in {
        "arrival", "live",
    }
    place = primary_place_for_occurrence(occurrence)
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
            "place": {"id": str(place.pk), "name": place.name} if place else None,
            "activity": {
                "id": str(occurrence.activity_id),
                "title": occurrence.activity.title,
            }
        },
        "links": links,
        "capabilities": capabilities,
    }


def _source_selection_url(space_slug, kind, identity):
    """Existing read-only selection; the Space Work API revalidates the scope."""
    return (
        reverse("organizations_api:workspace-work", kwargs={"slug": space_slug})
        + "?" + urlencode({"kind": kind, "id": str(identity)})
    )


def _offer_item(offer, caps, *, space_slug):
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
            "pricing": {
                "unit_price": str(offer.unit_price),
                "currency": offer.currency,
            },
            "activity": {
                "id": str(offer.activity_id),
                "title": offer.activity.title,
            }
        },
        "links": {
            "activity": f"/api/v1/activities/{offer.activity_id}/",
            "selection": _source_selection_url(space_slug, "offer", offer.pk),
        },
        "capabilities": _capabilities_for_activity(offer.activity_id, caps),
    }


def _journey_item(journey, caps, *, operator_case_url=None, space_slug=None):
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
            "work_label": (
                "Dossier de prestation"
                if journey.workflow == WorkflowKind.SERVICE else "Inscription"
            ),
        },
        "links": {
            "activity": f"/api/v1/activities/{journey.activity_id}/",
            **({"detail": operator_case_url} if operator_case_url else {}),
            **({
                "selection": _source_selection_url(space_slug, "journey", journey.pk),
            } if space_slug else {}),
        },
        "capabilities": _capabilities_for_activity(journey.activity_id, caps)
        + (["open_service_case"] if operator_case_url else []),
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
        # Never imply an executable transition without a verified owner action.
        "next": [],
    }
    return item


def _order_item(order, caps, *, space_slug):
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
        "links": {
            "activity": f"/api/v1/activities/{order.journey.activity_id}/",
            "detail": reverse(
                "organizations_api:workspace-commerce-order-detail",
                kwargs={"slug": space_slug, "order_id": order.pk},
            ),
        },
        "capabilities": _capabilities_for_activity(order.journey.activity_id, caps),
    }


def _route_item(route, *, space_slug):
    return {
        "key": f"transport_route:{route.pk}",
        "source": {"kind": "transport_route", "id": str(route.pk)},
        "kind": "route",
        "title": route.name,
        "summary": None,
        "timing": {},
        "state": "active" if route.active else "inactive",
        "context": {
            "stops": [
                {"id": str(stop.place_id), "name": stop.place.name,
                 "position": stop.position, "boarding_allowed": stop.boarding_allowed,
                 "alighting_allowed": stop.alighting_allowed}
                for stop in route.stops.all()
            ],
        },
        "links": {"selection": _source_selection_url(space_slug, "transport_route", route.pk)},
        "capabilities": ["view"],
    }


def _vehicle_item(vehicle, *, space_slug):
    return {
        "key": f"vehicle:{vehicle.pk}",
        "source": {"kind": "vehicle", "id": str(vehicle.pk)},
        "kind": "vehicle",
        "title": vehicle.label,
        "summary": None,
        "timing": {},
        "state": "active" if vehicle.active else "inactive",
        "context": {"passenger_capacity": vehicle.passenger_capacity},
        "links": {"selection": _source_selection_url(space_slug, "vehicle", vehicle.pk)},
        "capabilities": ["view"],
    }


def _empty_section(*, identity, role, representation, empty_message):
    return {
        "identity": identity,
        "representation": representation,
        "role": role,
        "coverage_state": "established",
        "items": [],
        "has_more": False,
        "links": {},
        "empty_message": empty_message,
    }


def _empty_sections(*, space, include_offers=False, include_transport=False, include_requests=False):
    grammar = work_presentation_for_space(space)
    roles = {
        "preparation": "continuity",
        "upcoming": "continuity",
        "active": "continuity",
        "blocked": "continuity",
        "completed": "history",
        "activities": "structure",
        "offers": "structure",
        "routes": "structure",
        "vehicles": "structure",
        "requests": "continuity",
    }
    fallback_labels = {
        "preparation": "À préparer",
        "upcoming": "À venir",
        "active": "En cours",
        "blocked": "Bloqués",
        "completed": "Terminés",
        "activities": operating_preset_for_space(space).primary_business_label,
        "offers": "Offres",
        "routes": "Routes",
        "vehicles": "Véhicules",
        "requests": "Demandes",
    }
    keys = ["preparation", "upcoming", "active", "blocked", "completed", "activities"]
    if include_requests:
        keys.append("requests")
    if include_offers:
        keys.append("offers")
    if include_transport:
        keys.extend(("routes", "vehicles"))

    sections = {}
    for key in ordered_work_section_keys(space, keys):
        label = grammar.label_for(key, fallback_labels[key])
        sections[key] = _empty_section(
            identity=key,
            role=roles[key],
            representation=label,
            empty_message=grammar.empty_message_for(key, label),
        )
    return sections


def _append(section, item):
    if not section.get("_enabled", True):
        return
    seen = section.get("_seen", 0)
    section["_seen"] = seen + 1
    if seen < section.get("_offset", 0):
        return
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
    try:
        mandate = (
            current_mandates()
            .filter(profile=profile, pk=mandate_id)
            .filter(
                Q(scope_type=AuthorityScope.SPACE, space=space)
                | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=space)
            )
            .first()
        )
    except (DjangoValidationError, ValueError):
        return set()
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


def _selected(queryset, kind, source_kind, source_id):
    """Restrict an owner read to one identity before applying preview limits."""
    if not source_kind and not source_id:
        return queryset
    if source_kind != kind or not source_id:
        return queryset.none()
    try:
        return queryset.filter(pk=source_id)
    except (ValueError, DjangoValidationError):
        return queryset.none()


def build_space_work_projection(
    *, profile, space, responsibility_key=None, source_kind=None, source_id=None,
    section_key=None, offset=0
):
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
        and lens_ids is None
        and "transport" in visible_operational_footprint_for_space(space, profile).signals
    )
    commerce_visible = bool(visible_ids & caps["commerce"])
    education_ids = visible_ids & caps["requests"]
    # Archetype changes presentation, never the availability of an authorized
    # domain. A mixed Space may handle registrations and service cases alike.
    education_visible = bool(education_ids)
    service_ids = visible_ids & caps["service_cases"]
    service_visible = bool(service_ids)
    sections = _empty_sections(
        space=space,
        include_offers=commerce_visible,
        include_transport=transport_visible,
        include_requests=education_visible or service_visible,
    )
    if section_key and section_key not in sections:
        return None
    for key, section in sections.items():
        section["_enabled"] = not section_key or key == section_key
        section["_offset"] = offset if section_key else 0
    now = timezone.now()
    today = timezone.localdate()

    activities = Activity.objects.filter(space=space, pk__in=visible_ids).order_by("title", "pk")
    activities = _selected(activities, "activity", source_kind, source_id)
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

    next_occurrence_by_activity = {}
    occurrences = (
        Occurrence.objects.filter(activity__space=space, activity_id__in=visible_ids)
        .select_related("activity", "transport_departure")
        .prefetch_related("place_links__place")
        .order_by("start_date", "start_time", "pk")
    )
    occurrences = _selected(occurrences, "occurrence", source_kind, source_id)
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
        if (
            space.archetype in {
                "generic", "community", "education", "service_provider"
            }
            and target == "upcoming"
            and str(occurrence.activity_id) not in next_occurrence_by_activity
        ):
            # Source order is chronological. This is a real, permitted
            # Occurrence, not a synthetic Activity lifecycle or readiness.
            next_occurrence_by_activity[str(occurrence.activity_id)] = {
                "id": str(occurrence.pk),
                "label": occurrence.label or occurrence.activity.title,
                "start_date": occurrence.start_date,
                "start_time": occurrence.start_time,
                "timezone": occurrence.timezone,
            }
        _append(sections[target], _occurrence_item(occurrence, caps))

    commerce_activity_ids = visible_ids & caps["commerce"]
    offers = (
        Offer.objects.filter(activity_id__in=commerce_activity_ids)
        .select_related("activity")
        .order_by("activity_id", "name", "pk")
    )
    for offer in _selected(offers, "offer", source_kind, source_id):
        if offer.status == OfferStatus.DRAFT:
            target = "preparation"
        elif offer.status in {OfferStatus.ACTIVE, OfferStatus.INACTIVE}:
            target = "offers"
        elif offer.status == OfferStatus.ARCHIVED:
            target = "completed"
        else:
            continue
        _append(sections[target], _offer_item(offer, caps, space_slug=space.slug))

    if has_direct_space_permission(profile, space, PermissionCode.ORDERS_VIEW):
        orders = (
            CommerceOrder.objects.filter(
                payee_space=space,
                journey__activity_id__in=visible_ids,
            )
            .select_related("journey__activity")
            .order_by("-created_at", "pk")
        )
        orders = _selected(orders, "commerce_order", source_kind, source_id)
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
            _append(sections[target], _order_item(order, caps, space_slug=space.slug))

    if education_ids:
        journeys = (
            Journey.objects.filter(
                activity_id__in=education_ids,
                workflow=WorkflowKind.REGISTRATION,
            )
            .select_related("activity")
            .prefetch_related("blockers")
            .order_by("-created_at", "pk")
        )
        for journey in _selected(journeys, "journey", source_kind, source_id):
            if (
                education_visible
                and journey.status in {
                    JourneyStatus.SUBMITTED,
                    JourneyStatus.PENDING_APPROVAL,
                }
            ):
                target = "requests"
            else:
                target = _journey_section(journey)
            if target:
                _append(sections[target], _journey_item(
                    journey, caps, space_slug=space.slug,
                ))

    # A Journey awaiting approval is not proof that a decision Request exists.
    # Link to the canonical JourneyRequest owner only when that exact owner is
    # currently present. The owner endpoint rechecks permission and expiry.
    registration_rows = [
        item for section in sections.values() for item in section["items"]
        if (
            item["source"]["kind"] == "journey"
            and item["context"].get("workflow") == WorkflowKind.REGISTRATION
        )
    ]
    if registration_rows:
        registration_ids = [row["source"]["id"] for row in registration_rows]
        owner_requests = (
            JourneyRequest.objects.filter(
                journey_id__in=registration_ids,
                journey__activity_id__in=education_ids,
                journey__workflow=WorkflowKind.REGISTRATION,
                status=RequestStatus.PENDING,
            )
            .order_by("-created_at", "pk")
            .values("journey_id", "pk")
        )
        request_by_journey = {}
        for request in owner_requests:
            request_by_journey.setdefault(
                str(request["journey_id"]), request["pk"]
            )
        for row in registration_rows:
            request_id = request_by_journey.get(row["source"]["id"])
            if request_id:
                row["links"]["request_detail"] = (
                    reverse(
                        "organizations_api:workspace-request-detail",
                        kwargs={"slug": space.slug, "request_id": request_id},
                    ) + "?" + urlencode({
                        "responsibility": responsibility_key or "all",
                    })
                )
                row["capabilities"].append("open_request")

    if service_ids:
        journeys = (
            service_journeys_visible_to(profile)
            .filter(activity_id__in=service_ids)
            .select_related("activity", "service_context")
            .prefetch_related("blockers")
        )
        for journey in _selected(journeys, "journey", source_kind, source_id):
            if (
                service_visible
                and journey.status in {
                    JourneyStatus.SUBMITTED,
                    JourneyStatus.PENDING_APPROVAL,
                }
            ):
                target = "requests"
            else:
                target = _journey_section(journey)
            if target:
                case_scope = service_case_scope(profile, journey)
                operator_case_url = (
                    reverse("services:operator-case", kwargs={"pk": journey.pk})
                    if (
                        case_scope in {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}
                        and hasattr(journey, "service_context")
                    )
                    else None
                )
                item = _journey_item(
                    journey, caps, operator_case_url=operator_case_url,
                    space_slug=space.slug,
                )
                if operator_case_url:
                    item["context"]["service_outcome"] = (
                        journey.service_context.current_outcome
                    )
                _append(sections[target], item)

    if transport_visible:
        routes = TransportRoute.objects.filter(space=space).prefetch_related("stops__place").order_by("name", "pk")
        for route in _selected(routes, "transport_route", source_kind, source_id):
            _append(sections["routes"], _route_item(route, space_slug=space.slug))
        vehicles = Vehicle.objects.filter(space=space).order_by("label", "pk")
        for vehicle in _selected(vehicles, "vehicle", source_kind, source_id):
            _append(sections["vehicles"], _vehicle_item(vehicle, space_slug=space.slug))

    # Only authorized operator case previews receive owner assessment counts.
    # Never serialize evidence, notes, beneficiary or inferred Readiness here.
    operator_rows = [
        item
        for section in sections.values()
        for item in section["items"]
        if (
            item["kind"] == "service_case"
            and "open_service_case" in item["capabilities"]
        )
    ]
    if operator_rows:
        case_ids = [row["source"]["id"] for row in operator_rows]
        assessments = (
            ServiceRequirementAssessment.objects
            .filter(context__journey_id__in=case_ids)
            .values("context__journey_id")
            .annotate(
                total=Count("pk"),
                satisfied=Count(
                    "pk", filter=Q(status=RequirementAssessmentState.SATISFIED)
                ),
                awaiting=Count(
                    "pk", filter=Q(status__in=(
                        RequirementAssessmentState.UNASSESSED,
                        RequirementAssessmentState.PENDING,
                    ))
                ),
                unsatisfied=Count(
                    "pk", filter=Q(status=RequirementAssessmentState.UNSATISFIED)
                ),
            )
        )
        by_case = {
            str(row["context__journey_id"]): row for row in assessments
        }
        for item in operator_rows:
            summary = by_case.get(item["source"]["id"])
            if summary is not None:
                item["context"]["conditions"] = {
                    "total": summary["total"],
                    "satisfied": summary["satisfied"],
                    "awaiting": summary["awaiting"],
                    "unsatisfied": summary["unsatisfied"],
                    # Owner assessments are facts, not a global ready/block flag.
                    "basis": "service_requirement_assessment",
                }

    # Keep the lasting Activity recognizable through its next known realization
    # without creating an "ongoing" state for a merely published Activity.
    if space.archetype in {
        "generic", "community", "education", "service_provider"
    }:
        for item in sections["activities"]["items"]:
            activity_id = item["source"]["id"]
            next_occurrence = next_occurrence_by_activity.get(
                activity_id
            )
            if next_occurrence is not None:
                item["context"]["next_occurrence"] = next_occurrence

    footprint = (
        list(visible_operational_footprint_for_space(space, profile).signals)
        if direct_portfolio
        else []
    )
    for section in sections.values():
        section.pop("_enabled", None)
        section.pop("_offset", None)
        section.pop("_seen", None)
    if section_key:
        sections = {section_key: sections[section_key]}

    # Non-persistent Business World for each implemented composition group.
    # It only references items already filtered by owner selectors.
    business_world = compose_space_work_business_world(
        archetype=space.archetype,
        label=preset.primary_business_label,
        sections=sections,
        limited=not direct_portfolio or lens_ids is not None,
        is_root=not (source_kind or source_id or section_key or offset),
    )
    reading_order = (
        [
            key
            for group in business_world["reading_groups"]
            for key in group["section_keys"]
        ]
        if business_world else list(sections)
    )

    return {
        "space": {
            "id": str(space.pk),
            "slug": space.slug,
            "name": space.name,
        },
        "archetype": space.archetype,
        "primary_business_label": preset.primary_business_label,
        "presentation": {
            "empty_message": work_presentation_for_space(space).surface_empty_message,
            "section_order": reading_order,
            **({
                "question": business_world["question"],
                "calm_message": business_world["calm_message"],
                "reading_groups": business_world["reading_groups"],
                "next_occurrence_label": (
                    "Prochaine action"
                    if space.archetype == "community"
                    else "Prochaine session" if space.archetype == "education"
                    else "Prochaine réalisation" if space.archetype == "service_provider"
                    else "Prochaine date"
                ),
            } if business_world else {}),
        },
        **({"business_world": business_world} if business_world else {}),
        "authority": {
            "scope": "space" if direct_portfolio else "activity_limited",
            "limited_to_activities": not direct_portfolio,
        },
        "responsibility": responsibility_key or "all",
        "operational_footprint": {"signals": footprint},
        "composition_state": "established",
        "coverage_state": "established" if direct_portfolio else "partial",
        "sections": sections,
        "page": {"offset": offset if section_key else 0, "limit": PREVIEW_LIMIT},
        "selection": next(
            (item for section in sections.values() for item in section["items"]),
            None,
        ) if source_kind or source_id else None,
        "links": {
            "workspace": f"/api/v1/organizations/workspaces/{space.slug}/",
        },
        "capabilities": {
            "create_activity": has_direct_space_permission(
                profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE
            ),
        },
    }

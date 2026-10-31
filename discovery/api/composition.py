from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit

from dataclasses import dataclass
from types import SimpleNamespace

from django.core import signing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from core.participant_selectors import participant_state_context
from core.personal_surface_orchestration import pass_discovery_candidates_through_molongo
from funding.discovery import (
    present_funding_card,
    public_funding_discovery_item,
    public_funding_discovery_items,
)
from opportunities.models import OpportunitySave
from opportunities.services import save_opportunity, unsave_opportunity

from discovery.card_contract import (
    present_occurrence_card,
    present_opportunity_card,
    present_service_card,
)
from discovery.intent import DiscoveryIntent, resolve_discovery_intent
from discovery.intelligence import interpret_with_intelligence
from discovery.models import ActivityBookmark
from discovery.presentation import aggregate_discovery_items, build_discovery_item
from discovery.search import (
    public_occurrences_for_activities,
    search_occurrences,
)
from discovery.unified import (
    public_opportunity_discovery_item,
    public_opportunity_discovery_items,
    public_service_discovery_item,
    public_service_discovery_items,
)

from .media_bindings import apply_recognition_media
from .projections import (
    project_funding_possibility,
    project_occurrence_possibility,
    project_opportunity_possibility,
    project_service_possibility,
)


DISCOVERY_API_PAGE_SIZE = 20
DISCOVERY_API_MAX_PAGE_SIZE = 50

DISCOVERY_CONTINUATION_SALT = "makolo.discovery.items.v1"
# Keep all public resource identities visible without embedding every full
# document in an N1 collection. Full TEXT lives at its owner read endpoint.
DISCOVERY_RESOURCE_INLINE_CHARS = 1400
DISCOVERY_RESOURCE_ACTIVITY_INLINE_BUDGET = 8400


def _safe_public_http_url(raw):
    if not isinstance(raw, str) or raw != raw.strip() or any(
        char in raw for char in "\r\n\t"
    ):
        return None
    try:
        parts = urlsplit(raw)
        if (
            parts.scheme.lower() not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            return None
    except ValueError:
        return None
    return raw


@dataclass(frozen=True)
class DiscoveryComposition:
    intent: DiscoveryIntent
    search_params: dict[str, str]
    rows: tuple
    timezone_name: str
    nearby_active: bool


def _authenticated(profile) -> bool:
    return bool(getattr(profile, "is_authenticated", False))


def _continuation_context(params, *, profile=None) -> str:
    """Bind a cursor to the exact request criteria and authenticated viewer.

    Page and continuation are navigation controls, not exploration criteria.
    No client-provided profile or authority is ever trusted.
    """
    if hasattr(params, "lists"):
        criteria = {
            key: sorted(str(value) for value in values)
            for key, values in params.lists()
            if key not in {"page", "continuation"}
        }
    else:
        criteria = {
            str(key): [str(value)]
            for key, value in params.items()
            if key not in {"page", "continuation"}
        }
    viewer = (
        str(profile.pk)
        if _authenticated(profile)
        else None
    )
    canonical = json.dumps(
        {"criteria": criteria, "viewer": viewer},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_page_params(params, *, profile=None) -> tuple[int, int]:
    """A request without parameters is valid; a cursor must match its context."""
    try:
        continuation = params.get("continuation")
        if continuation:
            cursor = signing.loads(
                continuation,
                salt=DISCOVERY_CONTINUATION_SALT,
                max_age=60 * 60 * 24,
            )
            if (
                not isinstance(cursor, dict)
                or cursor.get("context") != _continuation_context(
                    params, profile=profile
                )
            ):
                raise ValueError("Contexte de continuation incompatible.")
            page = max(int(cursor["page"]), 1)
        else:
            page = max(int(params.get("page") or 1), 1)
        page_size = min(
            max(int(params.get("page_size") or DISCOVERY_API_PAGE_SIZE), 1),
            DISCOVERY_API_MAX_PAGE_SIZE,
        )
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Pagination invalide ou continuation expiree.") from exc
    return page, page_size


def _empty_occurrence_result():
    from django.conf import settings

    return SimpleNamespace(
        items=[],
        timezone_name=settings.TIME_ZONE,
        total=0,
        nearby_active=False,
    )


def _combine_candidates(
    *,
    service_items,
    funding_items,
    opportunity_items,
    occurrence_items,
):
    """Use the same logical family composition as the mature Web surface."""
    rows = []
    seen = set()
    for family, candidates in (
        ("service_activity", service_items),
        ("funding_activity", funding_items),
        ("opportunity", opportunity_items),
        ("activity", occurrence_items),
    ):
        for candidate in candidates:
            key = (
                candidate["candidate_key"]
                if isinstance(candidate, dict)
                else candidate.candidate_key
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append((family, key, candidate))
    return tuple(rows)


def compose_discovery(params, *, profile=None) -> DiscoveryComposition:
    """Compose the actual mature Discovery field without ranking it.

    Search remains an open-field operation. This helper does not retrieve saved
    objects, create Journeys, infer Interests or expand the corpus to avoid a
    legitimate end of results.
    """

    intent = resolve_discovery_intent(params)
    intent = interpret_with_intelligence(intent, profile=profile)
    search_params = intent.to_search_params()
    vertical = intent.vertical

    occurrence_result = (
        _empty_occurrence_result()
        if vertical in {"service", "funding"}
        else search_occurrences(search_params, profile=profile)
    )
    service_items = public_service_discovery_items(
        search_params,
        profile=profile,
        requested_params=params,
        constraints=intent.constraints,
    )
    funding_items = public_funding_discovery_items(
        search_params,
        profile=profile,
        requested_params=params,
        constraints=intent.constraints,
    )
    opportunity_items = public_opportunity_discovery_items(
        search_params,
        requested_params=params,
        constraints=intent.constraints,
    )
    rows = _combine_candidates(
        service_items=service_items,
        funding_items=funding_items,
        opportunity_items=opportunity_items,
        occurrence_items=occurrence_result.items,
    )
    rows = pass_discovery_candidates_through_molongo(rows)
    return DiscoveryComposition(
        intent=intent,
        search_params=search_params,
        rows=rows,
        timezone_name=occurrence_result.timezone_name,
        nearby_active=bool(occurrence_result.nearby_active),
    )


def _saved_activity_ids(profile, activity_ids) -> set[str]:
    if not _authenticated(profile) or not activity_ids:
        return set()
    return {
        str(value)
        for value in ActivityBookmark.objects.filter(
            user=profile,
            activity_id__in=activity_ids,
        ).values_list("activity_id", flat=True)
    }


def _saved_opportunity_ids(profile, opportunity_ids) -> set[str]:
    if not _authenticated(profile) or not opportunity_ids:
        return set()
    return {
        str(value)
        for value in OpportunitySave.objects.filter(
            profile=profile,
            opportunity_id__in=opportunity_ids,
        ).values_list("opportunity_id", flat=True)
    }


def _activity_resource_previews(activity_ids, *, profile=None, occurrence_scope=None) -> dict[str, list[dict]]:
    """Expose authorized resource metadata, with a bounded inline TEXT sample.

    Preparation retains all document content, publication and reader authority.
    Discovery keeps *every* admitted resource identity, without a silent
    six-item or other presentation cutoff; long text is opened via read_url.
    """
    if not activity_ids:
        return {}
    from preparation.models import (
        ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility,
    )
    from preparation.services import can_view_resource

    rows = (
        ActivityResource.objects.filter(
            activity_id__in=activity_ids,
            status=ResourceStatus.PUBLISHED,
            visibility=ResourceVisibility.PUBLIC,
        )
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity_id", "title", "-version", "id")
    )
    result: dict[str, list[dict]] = {}
    remaining_by_activity = {}
    access_by_context = {}
    for resource in rows:
        activity_id = str(resource.activity_id)
        # A public occurrence-specific Resource for an unrelated session is
        # not a fact of the currently presented variant.
        if occurrence_scope is not None and resource.occurrence_id is not None:
            if str(resource.occurrence_id) not in occurrence_scope.get(activity_id, set()):
                continue
        # For published/public resources, delivery authority depends on the
        # Activity, viewer and occurrence context (not on the file type).
        # Cache that check, but never cache it across viewers or requests.
        access_key = (activity_id, str(resource.occurrence_id) if resource.occurrence_id else None)
        if access_key not in access_by_context:
            access_by_context[access_key] = can_view_resource(profile, resource)
        if not access_by_context[access_key]:
            continue
        bucket = result.setdefault(activity_id, [])
        text = resource.text_content if resource.kind == ResourceKind.TEXT else None
        truncated = False
        if text is not None:
            remaining = remaining_by_activity.get(
                activity_id, DISCOVERY_RESOURCE_ACTIVITY_INLINE_BUDGET,
            )
            excerpt = text[: min(DISCOVERY_RESOURCE_INLINE_CHARS, remaining)]
            truncated = len(excerpt) < len(text)
            remaining_by_activity[activity_id] = remaining - len(excerpt)
            text = excerpt
        bucket.append(
            {
                "id": str(resource.pk),
                "title": resource.title,
                "description": resource.description,
                "kind": resource.kind,
                "mime_type": resource.mime_type or None,
                "external_url": (
                    _safe_public_http_url(resource.external_url)
                    if resource.kind == ResourceKind.URL
                    else None
                ),
                "read_url": (
                    reverse(
                        "preparation:resource-text",
                        kwargs={"resource_id": resource.pk},
                    )
                    if resource.kind == ResourceKind.TEXT
                    else None
                ),
                "text_content": text,
                "text_truncated": truncated,
                "download_url": (
                    reverse(
                        "preparation:resource-download",
                        kwargs={"resource_id": resource.pk},
                    )
                    if resource.kind == ResourceKind.FILE
                    else None
                ),
            }
        )
    return result


def _opportunity_source_previews(opportunity_ids) -> dict[str, list[dict]]:
    if not opportunity_ids:
        return {}
    from opportunities.models import OpportunitySource, OpportunitySourceStatus

    sources = (
        OpportunitySource.objects.filter(
            opportunity_id__in=opportunity_ids,
            status=OpportunitySourceStatus.ACTIVE,
        )
        .order_by("opportunity_id", "-is_primary", "source_name", "id")
    )
    result: dict[str, list[dict]] = {}
    for source in sources:
        opportunity_id = str(source.opportunity_id)
        bucket = result.setdefault(opportunity_id, [])
        bucket.append(
            {
                "id": str(source.pk),
                "title": source.source_name,
                "description": "Source publique de référence.",
                "kind": "url",
                "mime_type": None,
                "external_url": _safe_public_http_url(source.url),
                "download_url": None,
            }
        )
    return result


def _public_occurrence_facts_for_rows(rows) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Resolve public occurrence-place roles for selected Activity candidates.

    Only Occurrences already admitted by Discovery can be inspected here.
    Reuse the same place-publication rule as Discovery's primary place.
    The bounded wire contains locations, not inferred routes or coordinates.
    """
    from django.core.exceptions import ObjectDoesNotExist
    from discovery.presentation import _space_place_is_public

    selected = {}
    for family, _, candidate in rows:
        if family != "activity":
            continue
        selected[str(candidate.activity_id)] = set(candidate.matching_occurrence_ids)

    if not selected:
        return {}, {}
    activity_ids = list(selected)
    occurrence_ids = {oid for ids in selected.values() for oid in ids}
    from activities.models import ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus

    # Exact identities have already passed the viewer-aware Discovery selector.
    # Only load place relations here, not Commerce/Capacity prefetches.
    queryset = (
        Occurrence.objects.filter(
            pk__in=occurrence_ids,
            activity_id__in=activity_ids,
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
            status=OccurrenceStatus.SCHEDULED,
        )
        .exclude(activity__space__verification_status="suspended")
        .select_related("activity", "activity__space", "activity__transport_service__route")
        .prefetch_related(
            "place_links__place",
            "activity__space__space_places",
            "activity__transport_service__route__stops__place",
        )
        .order_by("start_date", "start_time", "id")
    )
    facts = {activity_id: [] for activity_id in activity_ids}
    variants = {activity_id: [] for activity_id in activity_ids}
    for occurrence in queryset:
        activity_id = str(occurrence.activity_id)
        if str(occurrence.pk) not in selected.get(activity_id, set()):
            continue
        if len(variants[activity_id]) < 12:
            variants[activity_id].append({
                "occurrence": {"kind": "occurrence", "id": str(occurrence.pk)},
                "timing": {
                    "kind": occurrence.timing_kind,
                    "start_at": occurrence.start_at.isoformat() if occurrence.start_at else None,
                    "end_at": occurrence.end_at.isoformat() if occurrence.end_at else None,
                    "start_date": occurrence.start_date.isoformat() if occurrence.start_date else None,
                    "end_date": occurrence.end_date.isoformat() if occurrence.end_date else None,
                    "start_time": occurrence.start_time.isoformat() if occurrence.start_time else None,
                    "end_time": occurrence.end_time.isoformat() if occurrence.end_time else None,
                    "timezone": occurrence.timezone,
                },
            })
        bucket = facts[activity_id]
        if len(bucket) >= 12:
            continue
        for link in occurrence.place_links.all():
            place = link.place
            if not place.is_active or not _space_place_is_public(occurrence.activity, place):
                continue
            bucket.append({
                "occurrence": {"kind": "occurrence", "id": str(occurrence.pk)},
                "role": link.role,
                "place": {
                    "id": str(place.pk),
                    "name": place.name,
                    "locality": place.locality,
                    "latitude": float(place.latitude) if place.latitude is not None else None,
                    "longitude": float(place.longitude) if place.longitude is not None else None,
                },
            })
            if len(bucket) >= 12:
                break

        # Transport route stops are canonical multi-place facts even when an
        # Occurrence has no explicit place_links. Their original positions
        # determine departure/stopover/arrival; never reclassify after hiding
        # a non-public stop.
        if len(bucket) >= 12:
            continue
        try:
            service = occurrence.activity.transport_service
        except ObjectDoesNotExist:
            service = None
        if service is None:
            continue
        stops = list(service.route.stops.all())
        for index, stop in enumerate(stops):
            place = stop.place
            if not place.is_active or not _space_place_is_public(occurrence.activity, place):
                continue
            role = (
                "stop"
                if len(stops) == 1
                else "departure" if index == 0
                else "arrival" if index == len(stops) - 1
                else "stopover"
            )
            bucket.append({
                "occurrence": {"kind": "occurrence", "id": str(occurrence.pk)},
                "role": role,
                "place": {
                    "id": str(place.pk),
                    "name": place.name,
                    "locality": place.locality,
                    "latitude": float(place.latitude) if place.latitude is not None else None,
                    "longitude": float(place.longitude) if place.longitude is not None else None,
                },
            })
            if len(bucket) >= 12:
                break
    return facts, variants


def _assessment(projection: dict) -> list[dict]:
    facts = []
    availability = projection["availability"]["state"]
    if availability in {"sold_out", "closed", "cancelled", "completed"}:
        facts.append(
            {
                "state": "limiting",
                "code": availability,
                "label": {
                    "sold_out": "Plus de place disponible",
                    "closed": "Cette possibilité est close",
                    "cancelled": "Cette possibilité est annulée",
                    "completed": "Cette possibilité est terminée",
                }.get(availability, "Indisponible"),
                "provenance": "availability",
            }
        )
    elif availability in {"available", "unlimited", "open"}:
        facts.append(
            {
                "state": "favorable",
                "code": availability,
                "label": {
                    "available": "Disponible",
                    "unlimited": "Disponibilité sans limite connue",
                    "open": "Ouverte maintenant",
                }.get(availability, "Disponible"),
                "provenance": "availability",
            }
        )
    elif availability == "upcoming":
        facts.append(
            {
                "state": "unknown",
                "code": "not_open_yet",
                "label": "Pas encore ouverte",
                "provenance": "availability",
            }
        )
    else:
        facts.append(
            {
                "state": "unknown",
                "code": "availability_not_resolved",
                "label": "Disponibilité à confirmer",
                "provenance": "availability",
            }
        )

    relation = projection["personal_relation"]["state"]
    if relation == "access_valid":
        facts.append(
            {
                "state": "favorable",
                "code": "access_valid",
                "label": "Vous avez déjà le droit d’accès",
                "provenance": "personal_relation",
            }
        )
    elif relation == "unknown":
        facts.append(
            {
                "state": "unknown",
                "code": "personal_relation_not_resolved",
                "label": "Votre situation n’est pas encore déterminée ici",
                "provenance": "personal_relation",
            }
        )
    return facts


def _public_owner_facts(activity_ids, opportunity_ids) -> tuple[dict, dict]:
    """Batch owner identity and date facts without inferring ownership from created_by."""
    from accounts.models import UserProfile
    from activities.models import Activity
    from opportunities.models import Opportunity
    from organizations.models import SpaceLifecycle

    activities = list(
        Activity.objects.filter(pk__in=activity_ids)
        .select_related("space", "owner_profile")
    )
    profile_ids = [
        activity.owner_profile_id
        for activity in activities
        if activity.owner_profile_id is not None
    ]
    public_profiles = set(
        UserProfile.objects.filter(
            user_id__in=profile_ids,
            public_profile=True,
            searchable=True,
            user__is_active=True,
        ).values_list("user_id", flat=True)
    )
    activity_facts = {}
    for activity in activities:
        owner = None
        if activity.space_id is not None:
            space = activity.space
            if (
                space.public_profile
                and space.searchable
                and space.lifecycle == SpaceLifecycle.ACTIVE
                and space.verification_status != "suspended"
            ):
                owner = {
                    "display_name": space.name,
                    "identity": {"kind": "space", "id": str(space.pk)},
                    "representation": {"name": space.name, "avatar_url": None},
                    "context": {"city": space.city, "country": space.country},
                    "links": {
                        "public": reverse(
                            "organizer_public:detail",
                            kwargs={"slug": space.slug},
                        ),
                        "native": f"/spaces/{space.slug}",
                    },
                    "capabilities": ["view_public"],
                }
        elif activity.owner_profile_id in public_profiles:
            person = activity.owner_profile
            name = person.full_name or person.username
            owner = {
                "display_name": name,
                "identity": {"kind": "profile", "id": str(person.pk)},
                "representation": {
                    "name": name,
                    "avatar_url": person.avatar.url if person.avatar else None,
                },
                "context": {},
                "links": {
                    "public": reverse(
                        "account:public-profile",
                        kwargs={"profile_id": person.pk},
                    ),
                    "native": f"/people/{person.pk}",
                },
                "capabilities": ["view_public"],
            }
        activity_facts[str(activity.pk)] = {
            "owner": owner,
            "date": {
                "kind": "added_at",
                "label": "Ajouté le",
                "value": activity.created_at.isoformat(),
            },
        }

    opportunity_dates = {
        str(pk): published_at.isoformat() if published_at else None
        for pk, published_at in Opportunity.objects.filter(
            pk__in=opportunity_ids,
        ).values_list("pk", "published_at")
    }
    return activity_facts, opportunity_dates


def _service_handoffs(activity_ids, *, profile=None) -> dict[str, dict]:
    """A Service start is prevalidated and executed by Services, not Discovery."""
    if not activity_ids:
        return {}
    from services.views import public_services

    authenticated = _authenticated(profile)
    # The Activity has already passed public Discovery admission. Guests may
    # see the existence of a start path, never acquire the start capability.
    # Services remains the authority and revalidates upon authenticated entry.
    return {
        str(service.activity_id): {
            "state": "owner_api",
            "owner": "services",
            "capabilities": ["start"] if authenticated else ["start_after_auth"],
            "links": {
                "start": reverse(
                    "services-api:start", kwargs={"pk": service.pk},
                ),
            },
            "resource": {"kind": "service", "id": str(service.pk)},
            "presentation": (
                {} if authenticated else {
                    "capability": "start",
                    "label": "Commencer",
                    "enabled": False,
                    "requires_auth": True,
                }
            ),
        }
        for service in public_services().filter(activity_id__in=activity_ids)
    }


def _event_handoffs(activity_ids, *, profile=None) -> dict[str, dict]:
    if not activity_ids:
        return {}
    from django.db.models import Q, Sum
    from django.utils import timezone

    from capacity.models import CapacityReservation, CapacityReservationStatus
    from commerce.models import OfferStatus
    from events.models import Event
    from tickets.models import TicketType

    events = list(Event.objects.filter(activity_id__in=activity_ids))
    event_ids = [event.pk for event in events]
    ticket_types = (
        TicketType.objects.filter(
            event_id__in=event_ids,
            offer__status=OfferStatus.ACTIVE,
            capacity_pool__is_active=True,
            is_public=True,
        )
        .select_related("capacity_pool")
    )
    ticket_types = list(ticket_types)
    pool_ids = {ticket_type.capacity_pool_id for ticket_type in ticket_types}
    now = timezone.now()
    totals = {
        row["pool_id"]: (
            row["held"] or 0,
            row["committed"] or 0,
        )
        for row in CapacityReservation.objects.filter(pool_id__in=pool_ids)
        .values("pool_id")
        .annotate(
            held=Sum(
                "quantity",
                filter=Q(status=CapacityReservationStatus.HELD)
                & (
                    Q(expires_at__isnull=True)
                    | Q(expires_at__gt=now)
                ),
            ),
            committed=Sum(
                "quantity",
                filter=Q(status=CapacityReservationStatus.COMMITTED),
            ),
        )
    }
    types_by_event = {}
    for ticket_type in ticket_types:
        types_by_event.setdefault(ticket_type.event_id, []).append(ticket_type)

    def sold_out(ticket_type):
        total = ticket_type.capacity_pool.total_quantity
        if total is None:
            return False
        held, committed = totals.get(ticket_type.capacity_pool_id, (0, 0))
        return max(total - held - committed, 0) == 0

    authenticated = _authenticated(profile)
    result = {}
    for event in events:
        activity_id = str(event.activity_id)
        capabilities = ["inspect", "inspect_offers"]
        links = {
            "detail": reverse(
                "participant-event-detail",
                kwargs={"slug": event.slug},
            ),
            "offers": reverse(
                "participant-ticket-type-list",
                kwargs={"slug": event.slug},
            ),
            "orders": reverse("ticket-orders-list"),
        }
        public_types = types_by_event.get(event.pk, [])
        if public_types:
            links["native"] = f"/events/{event.slug}/tickets"
        if authenticated and any(
            sold_out(ticket_type)
            for ticket_type in public_types
        ):
            capabilities.append("join_waitlist")
            links["waitlist"] = reverse("ticket-waitlist-list")
        result[activity_id] = {
            "state": "owner_api",
            "owner": "events",
            "capabilities": capabilities,
            "links": links,
            "resource": {
                "kind": "event",
                "id": str(event.pk),
                "slug": event.slug,
            },
        }
    return result


def _obtention_handoffs(rows) -> dict[str, dict]:
    """Native Obtention routes only for admitted published Activity candidates."""
    from obtention.selectors import public_obtentions

    admitted = {
        str(candidate.activity_id)
        for family, _, candidate in rows
        if family == "activity"
    }
    if not admitted:
        return {}
    return {
        str(obtention.activity_id): {
            "state": "owner_api",
            "owner": "obtention",
            "capabilities": ["start_journey"],
            "links": {
                "detail": reverse("obtention_api:detail", kwargs={"pk": obtention.pk}),
                "start_journey": reverse("obtention_api:journey-create", kwargs={"pk": obtention.pk}),
                "native": f"/obtention/{obtention.pk}/choose",
            },
            "resource": {"kind": "obtention", "id": str(obtention.pk)},
        }
        for obtention in public_obtentions().filter(activity_id__in=admitted)
    }


def _funding_handoffs(rows) -> dict[str, dict]:
    """Use already-admitted Funding candidates and their owner service."""
    from funding.selectors import funding_accepts_contributions

    handoffs = {}
    for family, _, candidate in rows:
        if family != "funding_activity":
            continue
        funding = candidate["funding"]
        if not funding_accepts_contributions(funding):
            continue
        handoffs[str(candidate["activity_id"])] = {
            "state": "owner_api",
            "owner": "funding",
            "capabilities": ["contribute"],
            "links": {
                "detail": reverse("funding_api:public-detail", kwargs={"pk": funding.pk}),
                "contribute": reverse("funding_api:contribute", kwargs={"pk": funding.pk}),
                "native": f"/funding/{funding.pk}/contribute",
            },
            "resource": {"kind": "funding", "id": str(funding.pk)},
        }
    return handoffs


def _public_commerce_handoffs(activity_ids, *, profile=None):
    """Owner-side offer admission; never infer a booking from a description."""
    if not activity_ids:
        return {}
    from activities.models import Activity
    from commerce.models import Offer, OfferStatus
    from django.http import Http404
    from commerce.native_activity_checkout_api import (
        activity_offer_choices, public_activity_for_commerce,
    )
    # Discovery may contain many non-Commerce possibilities. Preselect the
    # owner-backed candidates before the more expensive capacity checks.
    offer_activity_ids = set(
        Offer.objects.filter(
            activity_id__in=activity_ids,
            status=OfferStatus.ACTIVE,
        ).values_list("activity_id", flat=True)
    )
    if not offer_activity_ids:
        return {}
    result = {}
    for activity in Activity.objects.filter(pk__in=offer_activity_ids).exclude(
        event_vertical__isnull=False
    ):
        try:
            public_activity_for_commerce(profile, activity.pk)
        except Http404:
            continue
        if not activity_offer_choices(activity):
            continue
        result[str(activity.pk)] = {
            "state": "owner_api",
            "owner": "commerce",
            "capabilities": ["inspect_offers"],
            "resource": {"kind": "activity", "id": str(activity.pk)},
            "links": {
                "offers": reverse("commerce_api:activity-checkout", kwargs={"activity_id": activity.pk}),
                "native": f"/commerce/activities/{activity.pk}/checkout",
            },
        }
    return result


def _personal_engagement_handoffs(activity_ids, *, profile=None):
    """Reuse the personal owner's confirmed Journey/Commerce relationships."""
    if not _authenticated(profile) or not activity_ids:
        return {}
    from commerce.native_checkout_api import personal_commerce_handoffs

    return personal_commerce_handoffs(activity_ids, actor=profile)


def _handoff_for_projection(
    projection: dict, *, event_handoffs=None, service_handoffs=None,
    funding_handoffs=None, obtention_handoffs=None,
    personal_handoffs=None, commerce_handoffs=None,
) -> dict:
    resource = projection["identity"]["resource"]
    family = projection["identity"]["family"]
    if family in {"activity", "service_activity", "funding_activity"} and personal_handoffs:
        handoff = personal_handoffs.get(resource["id"])
        if handoff is not None:
            occurrence = projection["identity"].get("occurrence")
            candidate_occurrence_id = occurrence.get("id") if isinstance(occurrence, dict) else None
            if not handoff.get("occurrence_id") or handoff["occurrence_id"] == candidate_occurrence_id:
                return handoff
    if family == "service_activity" and service_handoffs:
        handoff = service_handoffs.get(resource["id"])
        if handoff is not None:
            return handoff
    if family == "activity" and event_handoffs:
        handoff = event_handoffs.get(resource["id"])
        if handoff is not None:
            return handoff
    if family == "activity" and obtention_handoffs:
        handoff = obtention_handoffs.get(resource["id"])
        if handoff is not None:
            return handoff
    if family == "funding_activity" and funding_handoffs:
        handoff = funding_handoffs.get(resource["id"])
        if handoff is not None:
            return handoff
    if family == "activity" and commerce_handoffs:
        handoff = commerce_handoffs.get(resource["id"])
        if handoff is not None:
            return handoff
    return {
        "state": "owner_contract",
        "owner": {
            "service_activity": "services",
            "funding_activity": "funding",
            "opportunity": "opportunities",
        }.get(family, "activities"),
        "capabilities": [],
        "links": {},
    }


def _primary_action_for_projection(projection: dict) -> dict:
    """Select navigation from an owner-verified handoff, never from a title or price.

    Selection does not execute, reserve, charge or authorize anything. The
    destination owner must re-check eligibility and permission on entry.
    """
    engagement = projection["engagement"]
    capabilities = set(engagement.get("capabilities") or ())
    links = engagement.get("links") or {}
    resource = engagement.get("resource") or {}
    presentation = engagement.get("presentation") or {}
    if (
        engagement.get("owner") == "commerce"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "activity"
        and isinstance(resource.get("id"), str)
        and "inspect_offers" in capabilities
        and links.get("native") == f"/commerce/activities/{resource['id']}/checkout"
        and links.get("offers")
    ):
        return {
            "code": "inspect_offers",
            "label": "Choisir une offre",
            "icon": "shopping-bag",
            "destination": {"kind": "native", "path": links["native"]},
        }
    if (
        engagement.get("owner") == "commerce"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "commerce_order"
        and isinstance(resource.get("id"), str)
        and "resume_order" in capabilities
        and links.get("native") == f"/commerce/orders/{resource['id']}"
    ):
        return {
            "code": "resume_order",
            "label": "Ma commande",
            "icon": "receipt",
            "destination": {"kind": "native", "path": links["native"]},
        }
    if (
        engagement.get("owner") == "commerce"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "journey"
        and isinstance(resource.get("id"), str)
        and "checkout" in capabilities
        and links.get("native") == f"/commerce/journeys/{resource['id']}/checkout"
        and links.get("checkout")
    ):
        return {
            "code": "checkout",
            "label": "Choisir une offre",
            "icon": "shopping-bag",
            "destination": {"kind": "native", "path": links["native"]},
        }
    if (
        engagement.get("owner") == "journeys"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "journey"
        and isinstance(resource.get("id"), str)
        and "continue" in capabilities
        and links.get("native") == f"/journeys/{resource['id']}"
    ):
        return {
            "code": "continue",
            "label": "Continuer",
            "icon": "arrow",
            "destination": {"kind": "native", "path": links["native"]},
        }
    if (
        engagement.get("owner") == "services"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "service"
        and resource.get("id")
        and (
            (
                "start" in capabilities
                and presentation.get("capability") == "start"
                and presentation.get("enabled") is True
            )
            or (
                "start_after_auth" in capabilities
                and presentation.get("requires_auth") is True
                and presentation.get("capability") == "start"
            )
        )
        and links.get("start")
    ):
        return {
            "code": "start",
            "label": presentation.get("label") or "Commencer",
            "icon": "start",
            "destination": {
                "kind": "native",
                "path": f"/services/{resource['id']}/start",
            },
        }
    native = links.get("native")
    if (
        engagement.get("owner") == "events"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "event"
        and "inspect_offers" in capabilities
        and isinstance(native, str)
        and native.startswith("/events/")
        and native.endswith("/tickets")
    ):
        return {
            "code": "inspect_offers",
            "label": "Voir les billets",
            "icon": "ticket",
            "destination": {"kind": "native", "path": native},
        }
    if (
        engagement.get("owner") == "funding"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "funding"
        and isinstance(resource.get("id"), str)
        and "contribute" in capabilities
        and isinstance(native, str)
        and native == f"/funding/{resource['id']}/contribute"
        and links.get("contribute")
    ):
        return {
            "code": "contribute",
            "label": "Contribuer",
            "icon": "heart-handshake",
            "destination": {"kind": "native", "path": native},
        }
    if (
        engagement.get("owner") == "obtention"
        and engagement.get("state") == "owner_api"
        and resource.get("kind") == "obtention"
        and isinstance(resource.get("id"), str)
        and "start_journey" in capabilities
        and isinstance(native, str)
        and native == f"/obtention/{resource['id']}/choose"
        and links.get("start_journey")
    ):
        return {
            "code": "start_journey",
            "label": "Obtenir",
            "icon": "package-check",
            "destination": {"kind": "native", "path": native},
        }
    # Web uses the owner's presentation link independently. Discovery's
    # primary_action is for a verified in-app native route or N2 detail.
    return {
        "code": "detail",
        "label": "Détails",
        "icon": "arrow",
        "destination": {
            "kind": "detail",
            "path": projection["links"]["detail"],
        },
    }


def _finalize_projection(
    projection: dict,
    *,
    card=None,
    event_handoffs=None,
    service_handoffs=None,
    funding_handoffs=None,
    obtention_handoffs=None,
    personal_handoffs=None,
    commerce_handoffs=None,
    description="",
) -> dict:
    identity = projection["identity"]
    detail_url = reverse(
        "discovery_api:item-detail",
        kwargs={
            "family": identity["family"],
            "item_id": identity["resource"]["id"],
        },
    )
    owner_capabilities = [
        value
        for value in projection["capabilities"]
        if value != "view"
    ]
    projection["capabilities"] = list(dict.fromkeys(["view", *owner_capabilities]))
    owner_links = dict(projection.get("links") or {})
    projection["links"] = {
        **owner_links,
        "detail": detail_url,
        "saved": reverse(
            "discovery_api:item-saved",
            kwargs={
                "family": identity["family"],
                "item_id": identity["resource"]["id"],
            },
        ),
    }
    if card is not None:
        projection["links"]["web"] = card.url
        if card.actions.save is not None and card.actions.save.url:
            projection["links"]["web_saved"] = card.actions.save.url
        if card.actions.share is not None and card.actions.share.url:
            projection["links"]["web_share"] = card.actions.share.url
        projection["presentation_facts"] = [
            {
                "code": fact.code,
                "label": fact.label,
                "value": fact.value,
                "icon": fact.icon,
            }
            for fact in card.facts
        ]
        participant_state = getattr(card, "participant_state", None)
        participant_state_code = getattr(participant_state, "participant_state", None)
        if participant_state_code is not None:
            projection["participant_presentation"] = {
                "state": participant_state_code,
                "label": getattr(participant_state, "label", ""),
                "secondary_label": getattr(participant_state, "secondary_label", ""),
            }
    # Bind only owner-resolved public imagery already carried by the
    # canonical representation; a document is not a visual cover.
    image_url = projection["representation"].get("image_url")
    if image_url:
        projection["media_bindings"] = [{
            "resource": {"url": image_url},
            "target": dict(identity["resource"]),
            "purpose": "RECOGNIZE",
        }]
    projection["assessment"] = _assessment(projection)
    projection["engagement"] = _handoff_for_projection(
        projection,
        event_handoffs=event_handoffs,
        service_handoffs=service_handoffs,
        funding_handoffs=funding_handoffs,
        obtention_handoffs=obtention_handoffs,
        personal_handoffs=personal_handoffs,
        commerce_handoffs=commerce_handoffs,
    )
    if card is not None and card.actions.primary is not None:
        primary = card.actions.primary
        # A Web CTA may remain navigable without a matching owner API.
        # Do not advertise executable authority from presentation alone.
        executable = primary.code in projection["engagement"]["capabilities"]
        owner_presentation = projection["engagement"].get("presentation") or {}
        requires_auth = bool(owner_presentation.get("requires_auth"))
        projection["engagement"]["presentation"] = {
            "label": (
                owner_presentation.get("label") if requires_auth
                else primary.label
            ),
            "capability": (
                owner_presentation.get("capability") if requires_auth
                else primary.code
            ),
            "enabled": bool(not requires_auth and primary.enabled and executable),
            "requires_auth": requires_auth,
            "web": primary.url,
            "web_enabled": bool(primary.enabled and primary.url),
        }
    # One server-selected central action; old engagement fields remain stable.
    projection["engagement"]["primary_action"] = _primary_action_for_projection(
        projection
    )
    if description:
        projection["detail"] = {"description": description}
    return projection


def project_rows(rows, *, profile=None) -> list[dict]:
    activity_ids = {
        str(
            candidate["activity_id"]
            if isinstance(candidate, dict)
            else candidate.activity_id
        )
        for family, _, candidate in rows
        if family in {"activity", "service_activity", "funding_activity"}
    }
    opportunity_ids = {
        str(candidate["opportunity_id"])
        for family, _, candidate in rows
        if family == "opportunity"
    }
    from commerce.offer_price_facts import offer_price_facts_many

    price_contexts = {
        (
            str(candidate["activity_id"] if isinstance(candidate, dict) else candidate.activity_id),
            str(candidate.occurrence_id) if family == "activity" else None,
        )
        for family, _, candidate in rows
        if family in {"activity", "service_activity"}
    }
    owner_prices = offer_price_facts_many(contexts=price_contexts)
    # The collection and the existing detail API must expose the same
    # public description. Bulk-load it for the selected page only.
    from activities.models import Activity

    # Resolve published visual uses for this admitted page, in one bounded query.
    # A document Resource is never promoted into a cover.
    from groups.selectors import eligible_activity_ids_for_profile
    from presentations.media_models import PresentationMediaPurpose
    from presentations.media_selectors import public_presentation_media_for_activities

    admitted_activity_ids = eligible_activity_ids_for_profile(profile, activity_ids)
    presentation_activities = list(Activity.objects.filter(pk__in=admitted_activity_ids))
    candidate_occurrence_ids = {
        candidate.occurrence_id
        for family, _, candidate in rows
        if family == "activity" and candidate.occurrence_id is not None
    }
    from activities.models import Occurrence
    presentation_occurrences = list(Occurrence.objects.filter(
        pk__in=candidate_occurrence_ids,
        activity_id__in=admitted_activity_ids,
    ))
    presentation_uses = public_presentation_media_for_activities(
        presentation_activities,
        occurrences=presentation_occurrences,
        purpose=PresentationMediaPurpose.RECOGNIZE,
        profile=profile,
    )
    descriptions_by_activity = {
        str(activity_id): description
        for activity_id, description in Activity.objects.filter(
            pk__in=activity_ids
        ).values_list("pk", "description")
    }
    saved_activity_ids = _saved_activity_ids(profile, activity_ids)
    saved_opportunity_ids = _saved_opportunity_ids(profile, opportunity_ids)
    can_save = _authenticated(profile)
    event_handoffs = _event_handoffs(
        activity_ids,
        profile=profile,
    )
    service_handoffs = _service_handoffs(activity_ids, profile=profile)
    funding_handoffs = _funding_handoffs(rows)
    obtention_handoffs = _obtention_handoffs(rows)
    personal_handoffs = _personal_engagement_handoffs(activity_ids, profile=profile)
    commerce_handoffs = _public_commerce_handoffs(activity_ids, profile=profile)
    owner_facts, opportunity_dates = _public_owner_facts(
        activity_ids, opportunity_ids,
    )
    resource_occurrence_scope = {activity_id: set() for activity_id in activity_ids}
    for family, _, candidate in rows:
        if family == "activity":
            resource_occurrence_scope[str(candidate.activity_id)].update(
                str(value) for value in candidate.matching_occurrence_ids
            )
    activity_resources = _activity_resource_previews(
        activity_ids, profile=profile, occurrence_scope=resource_occurrence_scope,
    )
    opportunity_resources = _opportunity_source_previews(opportunity_ids)
    public_spatial_facts, occurrence_variants = _public_occurrence_facts_for_rows(rows)

    projections = []
    for family, _, candidate in rows:
        if family == "activity":
            saved = (
                str(candidate.activity_id) in saved_activity_ids
                if can_save
                else None
            )
            card = present_occurrence_card(candidate, bookmarked=bool(saved))
            projection = project_occurrence_possibility(
                candidate,
                card,
                saved=saved,
                can_save=can_save,
            )
        elif family == "service_activity":
            saved = (
                str(candidate["activity_id"]) in saved_activity_ids
                if can_save
                else None
            )
            card = present_service_card(candidate, bookmarked=bool(saved))
            projection = project_service_possibility(
                candidate,
                card,
                saved=saved,
                can_save=can_save,
            )
        elif family == "funding_activity":
            saved = (
                str(candidate["activity_id"]) in saved_activity_ids
                if can_save
                else None
            )
            card = present_funding_card(candidate, bookmarked=bool(saved))
            projection = project_funding_possibility(
                candidate,
                card,
                saved=saved,
                can_save=can_save,
            )
        elif family == "opportunity":
            saved = (
                str(candidate["opportunity_id"]) in saved_opportunity_ids
                if can_save
                else None
            )
            card = present_opportunity_card(candidate, saved=bool(saved))
            projection = project_opportunity_possibility(
                candidate,
                card,
                saved=saved,
                can_save=can_save,
            )
        else:
            continue
        description = (
            candidate.get("summary") or ""
            if family == "opportunity"
            else descriptions_by_activity.get(
                str(candidate["activity_id"] if isinstance(candidate, dict) else candidate.activity_id),
                "",
            )
        )
        finalized = _finalize_projection(
            projection,
            card=card,
            event_handoffs=event_handoffs,
            service_handoffs=service_handoffs,
            funding_handoffs=funding_handoffs,
            obtention_handoffs=obtention_handoffs,
            personal_handoffs=personal_handoffs,
            commerce_handoffs=commerce_handoffs,
            description=description,
        )
        if family == "opportunity":
            issuer_name = (candidate.get("issuer_name") or "").strip()
            finalized["owner"] = (
                {
                    "display_name": issuer_name,
                    "identity": {"kind": "external_issuer"},
                    "representation": {"name": issuer_name, "avatar_url": None},
                    "context": {},
                    "links": {},
                    "capabilities": [],
                }
                if issuer_name else None
            )
            published = opportunity_dates.get(str(candidate["opportunity_id"]))
            finalized["date"] = (
                {"kind": "published_at", "label": "Publiée le", "value": published}
                if published else None
            )
        else:
            facts = owner_facts.get(
                str(candidate["activity_id"] if isinstance(candidate, dict) else candidate.activity_id),
                {},
            )
            finalized["owner"] = facts.get("owner")
            finalized["date"] = facts.get("date")
        if family in {"activity", "service_activity", "funding_activity"}:
            current_activity_id = str(
                candidate["activity_id"] if isinstance(candidate, dict) else candidate.activity_id
            )
            current_occurrence_id = (
                str(candidate.occurrence_id)
                if family == "activity" and candidate.occurrence_id is not None
                else None
            )
            apply_recognition_media(
                finalized,
                presentation_uses.get(current_activity_id, ()),
                occurrence_id=current_occurrence_id,
            )
        if family in {"activity", "service_activity"}:
            key = (
                str(candidate["activity_id"] if isinstance(candidate, dict) else candidate.activity_id),
                str(candidate.occurrence_id) if family == "activity" else None,
            )
            owner_price = owner_prices.get(key)
            # Commerce is authoritative even when there is *no* applicable
            # Offer or multiple incompatible currencies. Never retain a
            # presentation-derived minimum in an owner 'unknown' state.
            if owner_price is not None:
                finalized["price"] = owner_price.as_dict()
        resource = finalized["identity"]["resource"]
        if family == "activity":
            finalized["spatial_facts"] = public_spatial_facts.get(
                str(candidate.activity_id), []
            )
            if candidate.matching_count > 1:
                finalized["variants"] = occurrence_variants.get(
                    str(candidate.activity_id), []
                )
        if resource["kind"] == "activity":
            finalized["resources"] = activity_resources.get(resource["id"], [])
        elif resource["kind"] == "opportunity":
            finalized["resources"] = opportunity_resources.get(resource["id"], [])
        else:
            finalized["resources"] = []
        projections.append(finalized)
    return projections


def paginated_projection(
    params,
    *,
    profile=None,
    include_internal_rows=False,
) -> dict:
    # Reject invalid/expired or cross-viewer continuations before executing
    # the expensive owner search and aggregation.
    page, page_size = parse_page_params(params, profile=profile)
    composition = compose_discovery(params, profile=profile)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = composition.rows[start:end]
    results = project_rows(page_rows, profile=profile)
    count = len(composition.rows)
    has_next = end < count
    authenticated = _authenticated(profile)
    profile_id = str(profile.pk) if authenticated else None
    observed_at = timezone.now()
    has_exploration = bool(
        composition.intent.raw_text or composition.intent.constraints
    )
    # Empty *page* is not an empty *field*: an out-of-range page must not
    # claim that the current criteria have no matching possibilities.
    field_empty = count == 0
    page_exhausted = count > 0 and not results
    selection_reason = None
    if field_empty:
        selection_reason = "no_match" if has_exploration else "no_current_proposal"
    payload = {
        "surface": "discover_me" if authenticated else "discover_public",
        "actor": (
            {"type": "profile", "id": profile_id}
            if authenticated
            else None
        ),
        "viewer": (
            {"type": "profile", "id": profile_id}
            if authenticated
            else None
        ),
        "freshness": {
            "state": "fresh",
            # Generation time, not proof that each owner fact was revalidated.
            "observed_at": observed_at.isoformat(),
            "generated_at": observed_at.isoformat(),
            "fact_freshness": "not_asserted",
        },
        "selection": {
            "state": "empty" if field_empty else "ready",
            "reason": selection_reason,
        },
        "capabilities": [],
        "handoffs": [],
        "count": count,
        "page": page,
        "page_size": page_size,
        "exploration": {
            "raw_text": composition.intent.raw_text,
            "search_params": dict(composition.search_params),
            "constraints": [
                {
                    "key": constraint.key,
                    "value": constraint.value,
                    "label": constraint.label,
                    "source": constraint.source.value,
                }
                for constraint in composition.intent.constraints
            ],
        },
        "has_next": has_next,
        "has_previous": page > 1 and count > 0,
        "timezone": composition.timezone_name,
        "nearby_active": composition.nearby_active,
        # `results` remains the supported legacy collection name while
        # `items` is the common C0 collection alias.
        "results": results,
        "items": results,
        "continuation": {
            "state": "more" if has_next else "end",
            "token": (
                signing.dumps(
                    {"page": page + 1, "context": _continuation_context(params, profile=profile)},
                    salt=DISCOVERY_CONTINUATION_SALT,
                    compress=True,
                )
                if has_next
                else None
            ),
            "watch": {
                "state": (
                    "available"
                    if _authenticated(profile)
                    else "authentication_required"
                ),
                "link": reverse("discovery_api:watches"),
            }
        },
        "terminal": {
            "state": ("empty" if field_empty else "end_of_field" if page_exhausted else "ok"),
            "message": None,
        },
    }
    if include_internal_rows:
        payload["_page_rows"] = page_rows
        payload["_all_rows"] = composition.rows
    return payload


def _activity_detail_candidate(activity_id, *, profile=None):
    from groups.selectors import filter_queryset_by_activity_group_eligibility

    queryset = public_occurrences_for_activities([activity_id])
    queryset = filter_queryset_by_activity_group_eligibility(queryset, profile)
    occurrences = list(queryset)
    if not occurrences:
        return None
    participant_context = participant_state_context(profile, occurrences)
    items = [
        build_discovery_item(
            occurrence,
            profile=profile,
            participant_context=participant_context,
        )
        for occurrence in occurrences
    ]
    aggregated = aggregate_discovery_items(items)
    return aggregated[0] if aggregated else None


def detail_candidate(family, item_id, *, profile=None):
    if family == "activity":
        item = _activity_detail_candidate(item_id, profile=profile)
        return ("activity", item) if item is not None else None
    if family == "service_activity":
        item = public_service_discovery_item(item_id, profile=profile)
        return ("service_activity", item) if item is not None else None
    if family == "funding_activity":
        item = public_funding_discovery_item(item_id, profile=profile)
        return ("funding_activity", item) if item is not None else None
    if family == "opportunity":
        item = public_opportunity_discovery_item(item_id)
        return ("opportunity", item) if item is not None else None
    return None


def detail_projection(family, item_id, *, profile=None) -> dict | None:
    candidate = detail_candidate(family, item_id, profile=profile)
    if candidate is None:
        return None
    family, item = candidate
    projection = project_rows(
        ((family, item["candidate_key"] if isinstance(item, dict) else item.candidate_key, item),),
        profile=profile,
    )[0]

    # The collection already carries the same authorized detail facts.
    # This endpoint stays available for refresh and direct links.
    return projection


def set_saved_state(family, item_id, *, profile, save: bool) -> dict | None:
    candidate = detail_candidate(family, item_id, profile=profile)
    if candidate is None:
        return None
    if family in {"activity", "service_activity", "funding_activity"}:
        activity_id = item_id
        if save:
            ActivityBookmark.objects.get_or_create(
                user=profile,
                activity_id=activity_id,
            )
        else:
            ActivityBookmark.objects.filter(
                user=profile,
                activity_id=activity_id,
            ).delete()
    elif family == "opportunity":
        from opportunities.selectors import published_opportunities

        opportunity = published_opportunities().filter(pk=item_id).first()
        if opportunity is None:
            return None
        if save:
            save_opportunity(profile=profile, opportunity=opportunity)
        else:
            unsave_opportunity(profile=profile, opportunity=opportunity)
    else:
        return None
    return detail_projection(family, item_id, profile=profile)

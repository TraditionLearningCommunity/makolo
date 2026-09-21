from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.urls import reverse

from core.participant_selectors import participant_state_context
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

from .projections import (
    project_funding_possibility,
    project_occurrence_possibility,
    project_opportunity_possibility,
    project_service_possibility,
)


DISCOVERY_API_PAGE_SIZE = 20
DISCOVERY_API_MAX_PAGE_SIZE = 50


@dataclass(frozen=True)
class DiscoveryComposition:
    intent: DiscoveryIntent
    search_params: dict[str, str]
    rows: tuple
    timezone_name: str
    nearby_active: bool


def _authenticated(profile) -> bool:
    return bool(getattr(profile, "is_authenticated", False))


def parse_page_params(params) -> tuple[int, int]:
    try:
        page = max(int(params.get("page") or 1), 1)
        page_size = min(
            max(int(params.get("page_size") or DISCOVERY_API_PAGE_SIZE), 1),
            DISCOVERY_API_MAX_PAGE_SIZE,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Pagination invalide.") from exc
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


def _event_handoffs(activity_ids) -> dict[str, dict]:
    if not activity_ids:
        return {}
    from events.models import Event

    rows = Event.objects.filter(activity_id__in=activity_ids).values(
        "activity_id",
        "slug",
    )
    result = {}
    for row in rows:
        activity_id = str(row["activity_id"])
        slug = row["slug"]
        result[activity_id] = {
            "state": "owner_api",
            "owner": "events",
            "capabilities": ["inspect", "inspect_offers"],
            "links": {
                "detail": reverse(
                    "participant-event-detail",
                    kwargs={"slug": slug},
                ),
                "offers": reverse(
                    "participant-ticket-type-list",
                    kwargs={"slug": slug},
                ),
                "orders": reverse("ticket-order-list"),
            },
        }
    return result


def _handoff_for_projection(projection: dict, *, event_handoffs=None) -> dict:
    resource = projection["identity"]["resource"]
    family = projection["identity"]["family"]
    if family == "activity" and event_handoffs:
        handoff = event_handoffs.get(resource["id"])
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


def _finalize_projection(
    projection: dict,
    *,
    event_handoffs=None,
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
    saved_capabilities = [
        value
        for value in projection["capabilities"]
        if value in {"save", "unsave"}
    ]
    projection["capabilities"] = ["view", *saved_capabilities]
    projection["links"] = {"detail": detail_url}
    projection["assessment"] = _assessment(projection)
    projection["engagement"] = _handoff_for_projection(
        projection,
        event_handoffs=event_handoffs,
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
    saved_activity_ids = _saved_activity_ids(profile, activity_ids)
    saved_opportunity_ids = _saved_opportunity_ids(profile, opportunity_ids)
    can_save = _authenticated(profile)
    event_handoffs = _event_handoffs(activity_ids)

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
        projections.append(
            _finalize_projection(
                projection,
                event_handoffs=event_handoffs,
            )
        )
    return projections


def paginated_projection(params, *, profile=None) -> dict:
    composition = compose_discovery(params, profile=profile)
    page, page_size = parse_page_params(params)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = composition.rows[start:end]
    results = project_rows(page_rows, profile=profile)
    count = len(composition.rows)
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "has_next": end < count,
        "has_previous": page > 1 and count > 0,
        "timezone": composition.timezone_name,
        "nearby_active": composition.nearby_active,
        "results": results,
        "continuation": {
            "watch": {
                "state": (
                    "available"
                    if _authenticated(profile)
                    else "authentication_required"
                ),
                "link": reverse("discovery_api:watches"),
            }
        },
    }


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

    if family == "activity":
        from activities.models import Activity

        activity = Activity.objects.filter(pk=item_id).only("description").first()
        description = activity.description if activity is not None else ""
    elif family == "service_activity":
        from services.models import ServiceDetails

        service = (
            ServiceDetails.objects.filter(activity_id=item_id)
            .select_related("activity")
            .only("activity__description")
            .first()
        )
        description = service.activity.description if service is not None else ""
    elif family == "funding_activity":
        description = item["funding"].activity.description
    else:
        description = item.get("summary") or ""

    if description:
        projection["detail"] = {"description": description}
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

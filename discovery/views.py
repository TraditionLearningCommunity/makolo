from datetime import datetime, time
from types import SimpleNamespace

from django.utils.dateparse import parse_date, parse_datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from activities.models import Activity, ActivityStatus, ActivityVisibility
from core.participant_selectors import participant_state_context
from core.web_navigation import safe_post_next
from funding.discovery import present_funding_card, public_funding_discovery_items
from opportunities.models import OpportunitySave
from social.models import ActionNeed, ActionNeedIntakePolicy, ActionNeedStatus, ActionNeedVisibility

from .card_contract import present_occurrence_card, present_opportunity_card, present_service_card
from .intelligence import interpret_with_intelligence
from .intent import AppliedConstraint, ConstraintSource, DiscoveryIntent, resolve_discovery_intent
from .models import ActivityBookmark
from .presentation import build_discovery_item, presenter_for
from .search import get_public_occurrence, public_occurrences_for_activities, search_occurrences
from .services import build_recommendations, public_discovery_events
from .api.composition import paginated_projection
from .telemetry import record_search
from .unified import public_opportunity_discovery_items, public_service_discovery_items


DISCOVERY_PAGE_SIZE = 24
DISCOVERY_PLACE_SUGGESTION_LIMIT = 10
DISCOVERY_FILTER_KEYS = (
    "q", "place", "city", "when", "period", "vertical", "price", "radius_km", "lat", "lon", "date", "date_from", "date_to", "ordering", "timezone",
)
_AVAILABILITY_LABELS = {
    "available": "Disponible",
    "unlimited": "Disponibilité sans limite connue",
    "open": "Ouverte maintenant",
    "sold_out": "Complet",
    "closed": "Close",
    "cancelled": "Annulée",
    "completed": "Terminée",
    "upcoming": "Pas encore ouverte",
    "unknown": "Disponibilité à confirmer",
}


def _place_suggestions(items, *, limit=DISCOVERY_PLACE_SUGGESTION_LIMIT):
    suggestions = []
    seen = set()
    for item in items:
        place = item.place
        if place is None:
            continue
        for candidate in (place.locality, place.name):
            value = (candidate or "").strip()
            key = value.casefold()
            if not value or key in seen:
                continue
            suggestions.append(value)
            seen.add(key)
            if len(suggestions) >= limit:
                return suggestions
    return suggestions


def _bookmarked_activity_ids(user, activity_ids=None):
    if not getattr(user, "is_authenticated", False):
        return set()
    queryset = ActivityBookmark.objects.filter(user=user)
    if activity_ids is not None:
        queryset = queryset.filter(activity_id__in=activity_ids)
    return set(queryset.values_list("activity_id", flat=True))


def _saved_opportunity_ids(user, opportunity_ids):
    if not getattr(user, "is_authenticated", False) or not opportunity_ids:
        return set()
    return set(
        OpportunitySave.objects.filter(
            profile=user,
            opportunity_id__in=opportunity_ids,
        ).values_list("opportunity_id", flat=True)
    )


def _query_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("focus", None)
    params.pop("_correction", None)
    return params.urlencode()


def _empty_occurrence_result():
    return SimpleNamespace(items=[], timezone_name=settings.TIME_ZONE, total=0, nearby_active=False)


def _combine_logical_candidates(*, service_items, funding_items, opportunity_items, occurrence_items):
    rows = []
    seen = set()
    for family, candidates in (
        ("service_activity", service_items),
        ("funding_activity", funding_items),
        ("opportunity", opportunity_items),
        ("occurrence", occurrence_items),
    ):
        for candidate in candidates:
            key = candidate["candidate_key"] if isinstance(candidate, dict) else candidate.candidate_key
            if key in seen:
                continue
            seen.add(key)
            rows.append((family, key, candidate))
    return rows


def _open_public_action_needs(activity):
    now = timezone.now()
    return list(
        ActionNeed.objects.filter(
            activity=activity,
            status=ActionNeedStatus.OPEN,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        .filter(Q(opens_at__isnull=True) | Q(opens_at__lte=now))
        .filter(Q(closes_at__isnull=True) | Q(closes_at__gt=now))
        .order_by("created_at", "id")
    )


def _discovery_intent_from_projection(exploration):
    params = dict(exploration.get("search_params") or {})
    constraints = tuple(
        AppliedConstraint(
            key=item["key"],
            value=item["value"],
            label=item["label"],
            source=ConstraintSource(item["source"]),
        )
        for item in exploration.get("constraints", [])
    )
    return DiscoveryIntent(
        raw_text=exploration.get("raw_text") or "",
        text=params.get("q", ""),
        vertical=params.get("vertical", ""),
        place=params.get("place", ""),
        when=params.get("when", ""),
        period=params.get("period", ""),
        price=params.get("price", ""),
        radius_km=params.get("radius_km", ""),
        lat=params.get("lat", ""),
        lon=params.get("lon", ""),
        date=params.get("date", ""),
        date_from=params.get("date_from", ""),
        date_to=params.get("date_to", ""),
        ordering=params.get("ordering", ""),
        timezone=params.get("timezone", ""),
        constraints=constraints,
    )


def _discovery_fact(code, label, value, icon=None):
    return SimpleNamespace(code=code, label=label, value=value, icon=icon)


def _discovery_first_person_action_label(label):
    """Humanize a confirmed owner Web action without changing its capability."""
    normalized = label.strip().casefold()
    return {
        "s'inscrire": "Je m'inscris",
        "s’inscrire": "Je m’inscris",
        "réserver": "Je réserve",
        "payer": "Je paye",
        "commander": "Je commande",
        "candidater": "Je candidate",
        "participer": "Je participe",
        "acheter": "J’achète",
        "louer": "Je loue",
        "demander": "Je demande",
        "contribuer": "Je contribue",
        "postuler": "Je postule",
    }.get(normalized, label)


def _added_date_label(value, *, now=None):
    """Friendly N1 added-at label; not an Occurrence date or guessed timestamp."""
    if not value:
        return ""
    instant = parse_datetime(str(value))
    if instant is None:
        day = parse_date(str(value)[:10])
        if day is None:
            return ""
        instant = timezone.make_aware(
            datetime.combine(day, time.min),
            timezone.get_current_timezone(),
        )
    if timezone.is_naive(instant):
        instant = timezone.make_aware(instant, timezone.get_current_timezone())
    current = now or timezone.now()
    local = timezone.localtime(instant)
    current = timezone.localtime(current)
    delta = current - local
    if delta.total_seconds() < 0:
        return local.strftime("%d/%m/%Y")
    days = (current.date() - local.date()).days
    if days == 0:
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return "À l’instant"
        if minutes < 60:
            return f"il y a {minutes} min"
        return f"il y a {int(delta.total_seconds() // 3600)} h"
    if days == 1:
        return "Hier"
    if days == 2:
        return "Avant-hier"
    if days < 7:
        return f"il y a {days} j"
    if days < 30:
        return f"il y a {days // 7} sem."
    return local.strftime("%d/%m/%Y")


def _web_discovery_card(item):
    identity = item["identity"]
    representation = item["representation"]
    links = item.get("links") or {}
    saved = item.get("saved") or {"state": "unknown"}
    engagement = item.get("engagement") or {}
    engagement_presentation = engagement.get("presentation") or {}

    # Classification is rendered under the title, never as a practical fact.
    type_labels = []
    def add_type(value):
        text = str(value or "").strip()
        if text and text.casefold() not in {label.casefold() for label in type_labels}:
            type_labels.append(text)

    add_type(representation.get("vertical_label"))
    add_type(representation.get("eyebrow"))
    facts = []
    seen = set()
    seen_labels = set()

    def canonical_code(code):
        normalized = str(code or "").strip().lower()
        return {
            "capacity": "availability",
            "start_at": "when",
            "start_date": "when",
            "place_primary": "place",
        }.get(normalized, normalized)

    def add_fact(code, label, value, icon):
        key = canonical_code(code)
        normalized_label = str(label or "").strip().casefold()
        if (
            value is None
            or not str(value).strip()
            or str(value).strip().casefold() in {"unknown", "inconnu", "inconnue", "n/a", "à confirmer"}
            or key in seen
            or normalized_label in seen_labels
        ):
            return
        seen.add(key)
        seen_labels.add(normalized_label)
        facts.append(_discovery_fact(key, label, value, icon))

    for fact in item.get("presentation_facts") or []:
        code = str(fact.get("code") or "fact")
        label = str(fact.get("label") or "")
        if code.casefold() == "type" or label.casefold() == "type":
            add_type(fact.get("value"))
        else:
            add_fact(code, label, fact.get("value"), fact.get("icon"))

    timing = item.get("timing") or {}
    place = item.get("place")
    price = item.get("price") or {}
    availability = item.get("availability") or {}

    if timing.get("start_at"):
        add_fact("when", "Quand", timing["start_at"], "calendar-clock")
    elif timing.get("start_date"):
        add_fact("when", "Quand", timing["start_date"], "calendar-clock")

    if place:
        place_value = place.get("name") or place.get("locality")
        if place.get("name") and place.get("locality") and place["locality"] != place["name"]:
            place_value = f"{place['name']}, {place['locality']}"
        if place_value:
            add_fact("place", "Lieu", place_value, "map-pin")

    if price.get("state") == "free":
        add_fact("price", "Prix", "Gratuit", "wallet-cards")
    elif price.get("minimum") is not None:
        price_value = str(price["minimum"])
        if (
            price.get("state") == "range"
            and price.get("maximum") is not None
            and price["maximum"] != price["minimum"]
        ):
            price_value = f"{price_value} – {price['maximum']}"
        elif price.get("state") in {"priced", "variant_dependent"}:
            price_value = f"À partir de {price_value}"
        if price.get("currency"):
            price_value = f"{price_value} {price['currency']}"
        add_fact("price", "Prix", price_value, "wallet-cards")

    availability_state = availability.get("state")
    if availability_state and availability_state != "unknown":
        add_fact(
            "availability",
            "Disponibilité",
            _AVAILABILITY_LABELS.get(availability_state, availability_state),
            "users",
        )
    temporal_labels = {
        "start_at": "Début",
        "start_date": "Début",
        "end_at": "Fin",
        "end_date": "Fin",
        "opens_at": "Ouverture",
        "closes_at": "Clôture",
        "deadline_at": "Date limite",
    }
    for fact in item.get("temporal_facts") or []:
        kind = fact.get("kind") or ""
        if kind in {"start_at", "start_date", "start_time"} and "when" in seen:
            continue
        if fact.get("value") is not None and kind in temporal_labels:
            add_fact(kind, temporal_labels[kind], fact["value"], "calendar-clock")

    spatial_labels = {
        "primary": "Lieu",
        "venue": "Lieu",
        "departure": "Départ",
        "arrival": "Arrivée",
        "stopover": "Escale",
        "boarding": "Embarquement",
        "dropoff": "Débarquement",
    }
    spatial_facts = item.get("spatial_facts") or []
    role_counts = {}
    for fact in spatial_facts:
        role = str(fact.get("role") or "").lower()
        role_counts[role] = role_counts.get(role, 0) + 1
    role_positions = {}
    for fact in spatial_facts:
        role = str(fact.get("role") or "").lower()
        place = fact.get("place") or {}
        if not isinstance(place, dict):
            continue
        name = str(place.get("name") or "").strip()
        locality = str(place.get("locality") or "").strip()
        display = f"{name}, {locality}" if name and locality and name.casefold() != locality.casefold() else (name or locality)
        if display:
            role_positions[role] = role_positions.get(role, 0) + 1
            repeated = role_counts[role] > 1
            ordinal = role_positions[role]
            code = (
                f"place_{role}_{ordinal}" if repeated
                else "place" if role in {"primary", "venue"} else f"place_{role}"
            )
            label = spatial_labels.get(role, "Lieu")
            if repeated:
                label = f"{label} {ordinal}"
            add_fact(code, label, display, "map-pin")

    save_action = None
    if links.get("web_saved"):
        is_saved = saved.get("state") == "saved"
        save_action = SimpleNamespace(
            code="unsave" if is_saved else "save",
            role="save",
            label="Enregistré" if is_saved else "J’enregistre",
            icon="orbit",
            state="saved" if is_saved else "available",
            url=links.get("web_saved"),
            emphasis="light",
            enabled=True,
        )

    primary_action = None
    if engagement_presentation.get("web"):
        primary_action = SimpleNamespace(
            code=engagement_presentation.get("capability") or "open",
            role="primary",
            label=_discovery_first_person_action_label(engagement_presentation.get("label") or "Continuer"),
            icon={
                "start": "play-circle",
                "reserve": "ticket",
                "book": "ticket",
                "register": "user-plus",
                "contribute": "hand-heart",
                "buy": "shopping-bag",
                "apply": "send",
            }.get(engagement_presentation.get("capability"), "external-link"),
            state="available",
            url=engagement_presentation["web"],
            emphasis="primary",
            enabled=bool(
                engagement_presentation.get(
                    "web_enabled", engagement_presentation.get("enabled", False)
                )
            ),
        )

    share_action = None
    if links.get("web_share"):
        share_action = SimpleNamespace(
            code="share",
            role="share",
            label="Partager",
            icon="share-2",
            state="available",
            url=links["web_share"],
            emphasis="light",
            enabled=True,
        )

    occurrence = identity.get("occurrence")
    owner = item.get("owner") or {}
    presentation_kind = representation.get("presentation_kind") or "generic"
    operator_label = {
        "event": "Organisé par",
        "transport": "Opéré par",
    }.get(presentation_kind, "Proposé par")

    added_date = None
    date_info = item.get("date") or {}
    if date_info.get("kind") == "added_at" and date_info.get("value"):
        value = str(date_info["value"])
        parsed = parse_datetime(value)
        if parsed is not None:
            added_date = timezone.localtime(parsed).date() if timezone.is_aware(parsed) else parsed.date()
        else:
            added_date = parse_date(value[:10])

    return SimpleNamespace(
        candidate_key=identity["candidate_key"],
        activity_id=(
            identity["resource"]["id"]
            if identity["resource"]["kind"] == "activity"
            else None
        ),
        occurrence_id=occurrence["id"] if occurrence else None,
        presentation_kind=presentation_kind,
        vertical_label=representation.get("vertical_label") or "Possibilité",
        type_labels=tuple(type_labels),
        date_display=added_date,
        added_label=_added_date_label(date_info.get("value")) if added_date else "",
        title=representation["title"],
        summary=representation.get("summary") or "",
        description=(item.get("detail") or {}).get("description") or "",
        operator_label=operator_label,
        operator_name=owner.get("display_name") or "",
        owner=owner,
        date=item.get("date"),
        representation=SimpleNamespace(**representation),
        facts=tuple(facts),
        resources=tuple(
            resource
            for resource in (item.get("resources") or [])
            if resource.get("title")
        ),
        gallery_media=tuple(
            media
            for media in (item.get("media_bindings") or [])
            if (media.get("resource") or {}).get("mime_type", "").startswith("image/")
            and (media.get("resource") or {}).get("url")
            and (media.get("resource") or {}).get("url") != representation.get("image_url")
        ),
        context_notes=tuple(
            fact.get("label")
            for fact in (item.get("assessment") or [])
            if fact.get("state") == "limiting" and fact.get("label")
        )[:2],
        variant_count=(len(item.get("variants") or []) if len(item.get("variants") or []) > 1 else 0),
        relation_count=len(item.get("relations") or []),
        participant_state=(
            SimpleNamespace(
                participant_state=item["participant_presentation"].get("state"),
                label=item["participant_presentation"].get("label"),
                secondary_label=item["participant_presentation"].get("secondary_label"),
            )
            if item.get("participant_presentation")
            else None
        ),
        actions=SimpleNamespace(
            save=save_action,
            primary=primary_action,
            share=share_action,
            secondary=(),
        ),
        url=links.get("web") or links.get("detail") or "#",
    )


class DiscoveryHomeView(TemplateView):
    template_name = "discovery/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["discovery_base_template"] = (
            "base/app.html"
            if self.request.user.is_authenticated
            else "base/public.html"
        )

        errors = []
        try:
            data = paginated_projection(
                self.request.GET,
                profile=self.request.user,
                include_internal_rows=True,
            )
        except ValidationError as exc:
            errors = list(exc.messages)
            data = {
                "count": 0,
                "page": 1,
                "page_size": DISCOVERY_PAGE_SIZE,
                "has_next": False,
                "has_previous": False,
                "timezone": settings.TIME_ZONE,
                "nearby_active": False,
                "results": [],
                "exploration": {
                    "raw_text": self.request.GET.get("q", ""),
                    "search_params": {},
                    "constraints": [],
                },
            }

        page_rows = tuple(data.pop("_page_rows", ()))
        all_rows = tuple(data.pop("_all_rows", ()))
        exploration = data.get("exploration") or {}
        intent = _discovery_intent_from_projection(exploration)
        results = data.get("results") or []
        discovery_cards = [_web_discovery_card(item) for item in results]

        paginator = Paginator(
            all_rows,
            max(int(data.get("page_size") or DISCOVERY_PAGE_SIZE), 1),
        )
        page_obj = paginator.get_page(data.get("page") or 1)
        page_service_items = [
            candidate for family, _, candidate in page_rows
            if family == "service_activity"
        ]
        page_opportunity_items = [
            candidate for family, _, candidate in page_rows
            if family == "opportunity"
        ]
        page_occurrence_items = [
            candidate for family, _, candidate in page_rows
            if family == "activity"
        ]
        family_by_key = {key: family for family, key, _ in page_rows}
        service_cards = [
            card for card in discovery_cards
            if family_by_key.get(card.candidate_key) == "service_activity"
        ]
        opportunity_cards = [
            card for card in discovery_cards
            if family_by_key.get(card.candidate_key) == "opportunity"
        ]

        filters = {
            key: self.request.GET.get(key, "")
            for key in DISCOVERY_FILTER_KEYS
        }
        filters["place"] = (
            self.request.GET.get("place")
            or self.request.GET.get("city")
            or ""
        )
        filters["period"] = intent.period

        occurrence_candidates = [
            candidate for family, _, candidate in all_rows
            if family == "activity"
        ]
        map_items = []
        place_suggestions = _place_suggestions(occurrence_candidates)
        for item in results if data.get("nearby_active") else ():
            place = item.get("place")
            identity = item.get("identity") or {}
            occurrence = identity.get("occurrence")
            if place:
                if (
                    occurrence
                    and place.get("latitude") is not None
                    and place.get("longitude") is not None
                ):
                    representation = item.get("representation") or {}
                    timing = item.get("timing") or {}
                    price = item.get("price") or {}
                    availability = item.get("availability") or {}
                    engagement = item.get("engagement") or {}
                    engagement_presentation = engagement.get("presentation") or {}
                    map_items.append(
                        {
                            "candidate_key": identity.get("candidate_key"),
                            "activity_id": identity.get("resource", {}).get("id"),
                            "occurrence_id": occurrence.get("id"),
                            "vertical": representation.get("presentation_kind") or "generic",
                            "title": representation.get("title"),
                            "timing_kind": timing.get("kind"),
                            "start_date": timing.get("start_date"),
                            "start_time": timing.get("start_time"),
                            "start_at": timing.get("start_at"),
                            "timezone": timing.get("timezone"),
                            "place": place,
                            "distance_km": place.get("distance_km"),
                            "price": {
                                "is_free": price.get("state") == "free",
                                "minimum": price.get("minimum"),
                                "currency": price.get("currency"),
                                "label": (
                                    "Gratuit"
                                    if price.get("state") == "free"
                                    else None
                                ),
                            },
                            "availability": {
                                "state": availability.get("state"),
                                "label": _AVAILABILITY_LABELS.get(
                                    availability.get("state"),
                                    availability.get("state") or "",
                                ),
                            },
                            "cta_label": engagement_presentation.get("label"),
                            "url": (item.get("links") or {}).get("web"),
                        }
                    )

        record_search(
            result_count=data.get("count", 0),
            constraint_count=len(intent.constraints),
            vertical=intent.vertical,
            nearby_active=bool(data.get("nearby_active")),
            had_query=bool((self.request.GET.get("q") or "").strip()),
            correction_key=self.request.GET.get("_correction", ""),
            error_count=len(errors),
        )

        context.update(
            {
                "items": page_occurrence_items,
                "service_items": page_service_items,
                "opportunity_items": page_opportunity_items,
                "cards": discovery_cards,
                "service_cards": service_cards,
                "opportunity_cards": opportunity_cards,
                "discovery_cards": discovery_cards,
                "page_obj": page_obj,
                "filters": filters,
                "discovery_intent": intent,
                "applied_constraints": intent.constraints,
                "search_errors": errors,
                "search_timezone": data.get("timezone") or settings.TIME_ZONE,
                "result_count": data.get("count", 0),
                "mappable_result_count": sum(
                    1
                    for candidate in occurrence_candidates
                    if candidate.to_map_dict() is not None
                ),
                "place_suggestions": place_suggestions[:DISCOVERY_PLACE_SUGGESTION_LIMIT],
                "nearby_active": bool(data.get("nearby_active")),
                "map_items": map_items,
                "bookmarked_activity_ids": {
                    item["identity"]["resource"]["id"]
                    for item in results
                    if item["identity"]["resource"]["kind"] == "activity"
                    and (item.get("saved") or {}).get("state") == "saved"
                },
                "saved_opportunity_ids": {
                    item["identity"]["resource"]["id"]
                    for item in results
                    if item["identity"]["resource"]["kind"] == "opportunity"
                    and (item.get("saved") or {}).get("state") == "saved"
                },
                "pagination_query": _query_without_page(self.request),
                "map_config": {
                    "tile_url": settings.MAP_TILE_URL,
                    "attribution": settings.MAP_TILE_ATTRIBUTION,
                    "max_zoom": settings.MAP_TILE_MAX_ZOOM,
                },
            }
        )
        return context


class DiscoveryActivityDetailView(TemplateView):
    template_name = "discovery/activity_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["discovery_base_template"] = "base/app.html" if self.request.user.is_authenticated else "base/public.html"
        try:
            occurrence = get_public_occurrence(kwargs["occurrence_id"])
        except ObjectDoesNotExist as exc:
            raise Http404 from exc
        presenter = presenter_for(occurrence)
        if presenter.key != "other":
            raise Http404
        participant_context = participant_state_context(self.request.user, [occurrence])
        context["item"] = build_discovery_item(occurrence, profile=self.request.user, participant_context=participant_context)
        context["occurrence"] = occurrence
        context["is_bookmarked"] = occurrence.activity_id in _bookmarked_activity_ids(self.request.user)
        context["help_needs"] = _open_public_action_needs(occurrence.activity)
        return context


class ForYouView(TemplateView):
    template_name = "discovery/for_you.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recommendations"] = build_recommendations(self.request.user, limit=24)
        context["bookmarked_activity_ids"] = _bookmarked_activity_ids(self.request.user)
        return context


class BookmarkListView(LoginRequiredMixin, ListView):
    model = ActivityBookmark
    template_name = "discovery/bookmarks.html"
    context_object_name = "bookmarks"
    paginate_by = 30
    login_url = "core:login"

    def get_queryset(self):
        return ActivityBookmark.objects.filter(user=self.request.user).select_related("activity", "activity__space", "activity__owner_profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bookmarks = list(context["bookmarks"])
        activity_ids = [bookmark.activity_id for bookmark in bookmarks]
        occurrences = list(public_occurrences_for_activities(activity_ids))
        first_by_activity = {}
        for occurrence in occurrences:
            first_by_activity.setdefault(occurrence.activity_id, occurrence)
        participant_context = participant_state_context(self.request.user, occurrences)
        rows = []
        for bookmark in bookmarks:
            occurrence = first_by_activity.get(bookmark.activity_id)
            item = None
            if occurrence is not None:
                item = build_discovery_item(occurrence, profile=self.request.user, participant_context=participant_context)
            rows.append({"bookmark": bookmark, "item": item})
        context["bookmark_rows"] = rows
        context["bookmarked_activity_ids"] = set(activity_ids)
        return context


class BookmarkToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, activity_id=None, event_id=None):
        if activity_id is not None:
            activity = get_object_or_404(
                Activity.objects.filter(status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC),
                pk=activity_id,
            )
        else:
            event = get_object_or_404(public_discovery_events(), pk=event_id)
            activity = event.activity
        bookmark, created = ActivityBookmark.objects.get_or_create(user=request.user, activity=activity)
        if created:
            messages.success(request, "Activité enregistrée.")
        else:
            bookmark.delete()
            messages.info(request, "Activité retirée de vos enregistrés.")
        return redirect(safe_post_next(request, fallback="discovery:home"))


class MyEventsView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        messages.info(request, "Retrouvez désormais vos démarches, accès, activités organisées et enregistrés dans les espaces dédiés.")
        return redirect("core:participant-home")

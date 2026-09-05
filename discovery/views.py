from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView

from activities.models import Activity, ActivityStatus, ActivityVisibility
from core.participant_selectors import participant_state_context

from .intelligence import interpret_with_intelligence
from .intent import resolve_discovery_intent
from .models import ActivityBookmark
from .presentation import build_discovery_item, presenter_for
from .search import get_public_occurrence, public_occurrences_for_activities, search_occurrences
from .services import build_recommendations, public_discovery_events
from .telemetry import record_search
from .unified import public_opportunity_discovery_items, public_service_discovery_items


DISCOVERY_PAGE_SIZE = 24
DISCOVERY_PLACE_SUGGESTION_LIMIT = 10
DISCOVERY_FILTER_KEYS = (
    "q",
    "place",
    "city",
    "when",
    "period",
    "vertical",
    "price",
    "radius_km",
    "lat",
    "lon",
    "date",
    "date_from",
    "date_to",
    "ordering",
    "timezone",
)


def _place_suggestions(items, *, limit=DISCOVERY_PLACE_SUGGESTION_LIMIT):
    """Return a small, de-duplicated list from already-public search items."""
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


def _bookmarked_activity_ids(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(ActivityBookmark.objects.filter(user=user).values_list("activity_id", flat=True))


def _query_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("focus", None)
    params.pop("_correction", None)
    return params.urlencode()


def _empty_occurrence_result():
    return SimpleNamespace(items=[], timezone_name=settings.TIME_ZONE, total=0, nearby_active=False)


def _combine_logical_candidates(*, service_items, opportunity_items, occurrence_items):
    """Stable exact-identity composition before pagination.

    Candidate identity identifies the real possibility; provenance explains why
    it was surfaced. Related cross-family possibilities are not merged.
    """
    rows = []
    seen = set()
    for family, candidates in (
        ("service_activity", service_items),
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


class DiscoveryHomeView(TemplateView):
    template_name = "discovery/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        errors = []
        intent = resolve_discovery_intent(self.request.GET)
        intent = interpret_with_intelligence(intent, profile=self.request.user)
        search_params = intent.to_search_params()
        vertical = intent.vertical
        try:
            result = _empty_occurrence_result() if vertical == "service" else search_occurrences(
                search_params, profile=self.request.user
            )
        except ValidationError as exc:
            result = _empty_occurrence_result()
            errors = list(exc.messages)
        occurrence_items = result.items
        service_items = public_service_discovery_items(
            search_params,
            profile=self.request.user,
            requested_params=self.request.GET,
            constraints=intent.constraints,
        )
        opportunity_items = public_opportunity_discovery_items(
            search_params,
            requested_params=self.request.GET,
            constraints=intent.constraints,
        )
        logical_candidates = _combine_logical_candidates(
            service_items=service_items,
            opportunity_items=opportunity_items,
            occurrence_items=occurrence_items,
        )
        result_count = len(logical_candidates)
        page_obj = Paginator(logical_candidates, DISCOVERY_PAGE_SIZE).get_page(self.request.GET.get("page"))
        page_rows = page_obj.object_list
        page_service_items = [row[2] for row in page_rows if row[0] == "service_activity"]
        page_opportunity_items = [row[2] for row in page_rows if row[0] == "opportunity"]
        page_occurrence_items = [row[2] for row in page_rows if row[0] == "occurrence"]

        filters = {key: self.request.GET.get(key, "") for key in DISCOVERY_FILTER_KEYS}
        filters["place"] = self.request.GET.get("place") or self.request.GET.get("city") or ""
        filters["period"] = intent.period
        nearby_active = bool(result.nearby_active)
        map_items = []
        if nearby_active:
            map_items = [
                payload
                for item in page_occurrence_items
                if (payload := item.to_map_dict()) is not None
            ]
        mappable_result_count = sum(
            1
            for item in occurrence_items
            if item.to_map_dict() is not None
        )
        record_search(
            result_count=result_count,
            constraint_count=len(intent.constraints),
            vertical=intent.vertical,
            nearby_active=nearby_active,
            had_query=bool((self.request.GET.get("q") or "").strip()),
            correction_key=self.request.GET.get("_correction", ""),
            error_count=len(errors),
        )
        context.update(
            {
                "items": page_occurrence_items,
                "service_items": page_service_items,
                "opportunity_items": page_opportunity_items,
                "page_obj": page_obj,
                "filters": filters,
                "discovery_intent": intent,
                "applied_constraints": intent.constraints,
                "search_errors": errors,
                "search_timezone": result.timezone_name,
                "result_count": result_count,
                "mappable_result_count": mappable_result_count,
                "place_suggestions": _place_suggestions(occurrence_items),
                "nearby_active": nearby_active,
                "map_items": map_items,
                "bookmarked_activity_ids": _bookmarked_activity_ids(self.request.user),
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
        try:
            occurrence = get_public_occurrence(kwargs["occurrence_id"])
        except ObjectDoesNotExist as exc:
            raise Http404 from exc
        presenter = presenter_for(occurrence)
        if presenter.key != "other":
            raise Http404
        participant_context = participant_state_context(self.request.user, [occurrence])
        context["item"] = build_discovery_item(
            occurrence,
            profile=self.request.user,
            participant_context=participant_context,
        )
        context["occurrence"] = occurrence
        context["is_bookmarked"] = occurrence.activity_id in _bookmarked_activity_ids(self.request.user)
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
        return ActivityBookmark.objects.filter(user=self.request.user).select_related(
            "activity",
            "activity__space",
            "activity__owner_profile",
        )

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
                item = build_discovery_item(
                    occurrence,
                    profile=self.request.user,
                    participant_context=participant_context,
                )
            rows.append({"bookmark": bookmark, "item": item})
        context["bookmark_rows"] = rows
        context["bookmarked_activity_ids"] = set(activity_ids)
        return context


class BookmarkToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, activity_id=None, event_id=None):
        if activity_id is not None:
            activity = get_object_or_404(
                Activity.objects.filter(
                    status=ActivityStatus.PUBLISHED,
                    visibility=ActivityVisibility.PUBLIC,
                ),
                pk=activity_id,
            )
        else:
            event = get_object_or_404(public_discovery_events(), pk=event_id)
            activity = event.activity
        bookmark, created = ActivityBookmark.objects.get_or_create(user=request.user, activity=activity)
        if created:
            messages.success(request, "Activité ajoutée à vos favoris.")
        else:
            bookmark.delete()
            messages.info(request, "Activité retirée de vos favoris.")
        return redirect(request.POST.get("next") or "discovery:home")


class MyEventsView(LoginRequiredMixin, View):
    """Compatibility route for the retired Event-only participant hub."""

    login_url = "core:login"

    def get(self, request):
        messages.info(
            request,
            "Retrouvez désormais vos démarches, accès, activités organisées et favoris dans les espaces dédiés.",
        )
        return redirect("core:participant-home")

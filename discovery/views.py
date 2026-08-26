from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from activities.models import Activity, ActivityStatus, ActivityVisibility
from core.participant_selectors import participant_state_context

from .models import ActivityBookmark
from .presentation import build_discovery_item, presenter_for
from .search import get_public_occurrence, public_occurrences_for_activities, search_occurrences
from .services import build_recommendations, build_trending, public_discovery_events


DISCOVERY_PAGE_SIZE = 24
DISCOVERY_PLACE_SUGGESTION_LIMIT = 10
DISCOVERY_FILTER_KEYS = (
    "q",
    "place",
    "city",
    "when",
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


class DiscoveryHomeView(TemplateView):
    template_name = "discovery/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        errors = []
        try:
            result = search_occurrences(self.request.GET, profile=self.request.user)
        except ValidationError as exc:
            result = None
            errors = list(exc.messages)
        items = result.items if result else []
        page_obj = Paginator(items, DISCOVERY_PAGE_SIZE).get_page(self.request.GET.get("page"))
        filters = {key: self.request.GET.get(key, "") for key in DISCOVERY_FILTER_KEYS}
        filters["place"] = self.request.GET.get("place") or self.request.GET.get("city") or ""
        nearby_active = bool(result and result.nearby_active)
        map_items = []
        if nearby_active:
            map_items = [
                payload
                for item in page_obj.object_list
                if (payload := item.to_map_dict()) is not None
            ]
        context.update(
            {
                "items": page_obj.object_list,
                "page_obj": page_obj,
                "filters": filters,
                "search_errors": errors,
                "search_timezone": result.timezone_name if result else settings.TIME_ZONE,
                "result_count": result.total if result else 0,
                "place_suggestions": _place_suggestions(items),
                "nearby_active": nearby_active,
                "map_items": map_items,
                "bookmarked_activity_ids": _bookmarked_activity_ids(self.request.user),
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
        context["trending"] = build_trending(limit=12)
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

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from core.participant_selectors import participant_state_context
from tickets.models import Ticket, TicketOrderStatus

from .models import EventBookmark
from .presentation import build_discovery_item, presenter_for
from .search import get_public_occurrence, search_occurrences
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
        context.update(
            {
                "items": page_obj.object_list,
                "page_obj": page_obj,
                "filters": filters,
                "search_errors": errors,
                "search_timezone": result.timezone_name if result else settings.TIME_ZONE,
                "result_count": result.total if result else 0,
                "place_suggestions": _place_suggestions(items),
                "map_items": [
                    payload
                    for item in page_obj.object_list
                    if (payload := item.to_map_dict()) is not None
                ],
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
        return context


class ForYouView(TemplateView):
    template_name = "discovery/for_you.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recommendations"] = build_recommendations(self.request.user, limit=24)
        context["trending"] = build_trending(limit=12)
        if self.request.user.is_authenticated:
            context["bookmarked_ids"] = set(
                EventBookmark.objects.filter(user=self.request.user).values_list("event_id", flat=True)
            )
        else:
            context["bookmarked_ids"] = set()
        return context


class BookmarkListView(LoginRequiredMixin, ListView):
    model = EventBookmark
    template_name = "discovery/bookmarks.html"
    context_object_name = "bookmarks"
    paginate_by = 30
    login_url = "core:login"

    def get_queryset(self):
        return EventBookmark.objects.filter(user=self.request.user).select_related(
            "event",
            "event__activity",
            "event__activity__space",
            "event__category",
            "event__venue",
            "event__venue__place",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookmarked_ids"] = set(
            EventBookmark.objects.filter(user=self.request.user).values_list("event_id", flat=True)
        )
        return context


class BookmarkToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, event_id):
        event = get_object_or_404(public_discovery_events(), pk=event_id)
        bookmark, created = EventBookmark.objects.get_or_create(user=request.user, event=event)
        if created:
            messages.success(request, "Événement ajouté à vos favoris.")
        else:
            bookmark.delete()
            messages.info(request, "Événement retiré de vos favoris.")
        return redirect(request.POST.get("next") or "discovery:home")


class MyEventsView(LoginRequiredMixin, TemplateView):
    template_name = "discovery/my_events.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        tickets = Ticket.objects.filter(owner=self.request.user).select_related(
            "event",
            "event__activity",
            "event__activity__space",
            "ticket_type",
            "order",
            "access",
            "access__occurrence",
            "event__venue",
            "event__venue__place",
        )
        context["upcoming_tickets"] = tickets.filter(
            order__status=TicketOrderStatus.CONFIRMED,
            access__occurrence__end_at__gte=now,
        ).order_by("access__occurrence__start_at")
        context["past_tickets"] = tickets.filter(
            order__status=TicketOrderStatus.CONFIRMED,
            access__occurrence__end_at__lt=now,
        ).order_by("-access__occurrence__end_at")[:30]
        context["bookmarks"] = EventBookmark.objects.filter(user=self.request.user).select_related(
            "event",
            "event__activity",
            "event__activity__space",
        )[:12]
        context["followed_organizations"] = self.request.user.followed_organizations.select_related(
            "organization"
        )[:20]
        return context
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from tickets.models import Ticket, TicketOrderStatus

from .models import EventBookmark
from .services import build_recommendations, build_trending, public_discovery_events, search_discovery_events


class DiscoveryHomeView(TemplateView):
    template_name = "discovery/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["events"] = search_discovery_events(self.request.GET)[:40]
        context["trending"] = build_trending(limit=8)
        context["recommendations"] = build_recommendations(self.request.user, limit=8)
        context["filters"] = self.request.GET
        if self.request.user.is_authenticated:
            context["bookmarked_ids"] = set(
                EventBookmark.objects.filter(user=self.request.user).values_list("event_id", flat=True)
            )
        else:
            context["bookmarked_ids"] = set()
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

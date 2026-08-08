from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from .selectors import get_analytics_events
from .services import build_event_analytics, build_portfolio_analytics


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics"] = build_portfolio_analytics(self.request.user)
        return context


class EventAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/event_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(
            get_analytics_events(self.request.user),
            slug=self.kwargs["slug"],
        )
        try:
            days = int(self.request.GET.get("days", "30"))
        except ValueError:
            days = 30
        context["event"] = event
        context["analytics"] = build_event_analytics(event, self.request.user, days=days)
        context["days"] = min(max(days, 7), 90)
        return context

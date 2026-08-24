from django.db.models import Q

from .console_insights import (
    analytics_insights,
    automation_rules_insights,
    operations_insights,
    payments_insights,
)
from .console_selectors import incidents_for_console, payments_for_console
from .console_views import (
    SpaceConsoleAnalyticsView as BaseAnalyticsView,
    SpaceConsoleAutomationView as BaseAutomationView,
    SpaceConsoleOperationsView as BaseOperationsView,
    SpaceConsolePaymentsView as BasePaymentsView,
)


class SpaceConsoleAnalyticsView(BaseAnalyticsView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics"] = analytics_insights(self.space_console)
        return context


class SpaceConsolePaymentsView(BasePaymentsView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = payments_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        q = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if q:
            queryset = queryset.filter(
                Q(reference__icontains=q)
                | Q(commerce_order__reference__icontains=q)
                | Q(payer_name__icontains=q)
                | Q(payer_email__icontains=q)
            )
        context["page_obj"] = self.paginate(queryset)
        context["status_filter"] = status
        context["query"] = q
        context["payment_kpis"] = payments_insights(self.space_console)
        return context


class SpaceConsoleOperationsView(BaseOperationsView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = incidents_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        context["page_obj"] = self.paginate(queryset)
        context["status_filter"] = status
        context["operations"] = operations_insights(self.space_console)
        return context


class SpaceConsoleAutomationView(BaseAutomationView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_obj"] = self.paginate(automation_rules_insights(self.space_console))
        return context

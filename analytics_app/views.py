from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from partners.analytics import build_event_partner_analytics

from .event_adapter import build_event_analytics
from .forms import GrowthSpendForm
from .growth_contract import build_growth_portfolio, build_organization_growth
from .models import GrowthSpend
from .permissions import user_can_manage_growth_spend, user_can_view_event_financials
from .selectors import get_analytics_events, get_growth_organizations, get_growth_spends
from .services import build_portfolio_analytics


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics"] = build_portfolio_analytics(self.request.user)
        context["growth"] = build_growth_portfolio(self.request.user)
        return context


class EventAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/event_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(get_analytics_events(self.request.user), slug=self.kwargs["slug"])
        try:
            days = int(self.request.GET.get("days", "30"))
        except ValueError:
            days = 30
        context["event"] = event
        context["analytics"] = build_event_analytics(event, self.request.user, days=days)
        context["partner_analytics"] = build_event_partner_analytics(
            event,
            finance_visible=user_can_view_event_financials(self.request.user, event),
        )
        context["days"] = min(max(days, 7), 90)
        return context


class GrowthAnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/growth_dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["growth"] = build_growth_portfolio(self.request.user)
        return context


class OrganizationGrowthAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics_app/growth_organization_t30.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = get_object_or_404(
            get_growth_organizations(self.request.user), slug=self.kwargs["slug"]
        )
        try:
            months = int(self.request.GET.get("months", "12"))
        except ValueError:
            months = 12
        try:
            cohort_months = int(self.request.GET.get("cohorts", "6"))
        except ValueError:
            cohort_months = 6
        months = min(max(months, 3), 24)
        cohort_months = min(max(cohort_months, 3), 12)
        context["organization"] = organization
        context["growth"] = build_organization_growth(
            organization, self.request.user, months=months, cohort_months=cohort_months
        )
        context["months"] = months
        context["cohort_months"] = cohort_months
        context["can_manage_spend"] = user_can_manage_growth_spend(self.request.user, organization)
        return context


class GrowthSpendCreateView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "analytics_app/growth_spend_form.html"

    def _organization(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        if not user_can_manage_growth_spend(request.user, organization):
            raise PermissionDenied("Un rôle Finance, Owner ou Admin est requis pour gérer les dépenses Growth.")
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        form = GrowthSpendForm(organization=organization)
        return render(request, self.template_name, {"organization": organization, "form": form})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        form = GrowthSpendForm(request.POST, organization=organization)
        if form.is_valid():
            spend = form.save(commit=False)
            spend.organization = organization
            spend.created_by = request.user
            spend.save()
            messages.success(request, "Dépense Growth enregistrée dans sa devise d'origine.")
            return redirect("analytics:growth-organization", slug=organization.slug)
        return render(
            request, self.template_name, {"organization": organization, "form": form}, status=400
        )


class GrowthSpendDeleteView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        spend = get_object_or_404(get_growth_spends(request.user), pk=pk)
        organization = spend.organization
        if not user_can_manage_growth_spend(request.user, organization):
            raise PermissionDenied("Vous ne pouvez pas supprimer cette dépense Growth.")
        spend.delete()
        messages.success(request, "Dépense Growth supprimée.")
        return redirect("analytics:growth-organization", slug=organization.slug)

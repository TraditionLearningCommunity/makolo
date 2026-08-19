from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from access.services import revoke_access
from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can
from automation.services import ensure_policy
from events.forms import EventForm
from events.services import create_event
from journeys.services import approve_request, reject_request

from .console_context import SpaceConsoleContext
from .console_selectors import (
    accesses_for_console,
    activities_for_console,
    activity_for_console,
    analytics_summary,
    audiences_for_console,
    automation_rules_for_console,
    capacity_for_console,
    contacts_for_console,
    groups_for_console,
    incidents_for_console,
    offers_for_console,
    orders_for_console,
    overview_for_console,
    payments_for_console,
    places_for_console,
    promotions_for_console,
    requests_for_console,
    team_for_console,
)
from .models import Organization


class SpaceConsoleMixin(LoginRequiredMixin):
    login_url = "core:login"
    module_key = None
    page_title = "Vue d’ensemble"

    def dispatch(self, request, *args, **kwargs):
        self.space = get_object_or_404(Organization, slug=kwargs["slug"])
        self.space_console = SpaceConsoleContext.build(request.user, self.space)
        if self.space_console is None:
            raise PermissionDenied("Vous n'avez pas d'autorité active dans cet Espace.")
        if self.module_key and not self._module_is_visible(self.module_key):
            raise PermissionDenied("Cette responsabilité ne fait pas partie de votre Mandat dans cet Espace.")
        return super().dispatch(request, *args, **kwargs)

    def _module_is_visible(self, key):
        return any(
            item["key"] == key
            for group in self.space_console.navigation_groups
            for item in group["items"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "space": self.space,
                "organization": self.space,
                "space_console": self.space_console,
                "console_page_title": self.page_title,
                "console_module_key": self.module_key or "overview",
            }
        )
        return context

    def paginate(self, queryset, *, per_page=25):
        paginator = Paginator(queryset, per_page)
        return paginator.get_page(self.request.GET.get("page"))


class SpaceConsoleEntryView(SpaceConsoleMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect("organizations:console-overview", slug=self.space.slug)


class SpaceConsoleOverviewView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/overview.html"
    page_title = "Vue d’ensemble"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(overview_for_console(self.space_console))
        return context


class SpaceConsoleActivitiesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/activities.html"
    module_key = "activities"
    page_title = "Activités"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = activities_for_console(self.space_console)
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(short_description__icontains=q))
        if status:
            queryset = queryset.filter(status=status)
        context["page_obj"] = self.paginate(queryset)
        context["query"] = q
        context["status_filter"] = status
        context["can_create_activity"] = self.space_console.can_manage_activities
        return context


class SpaceConsoleActivityDetailView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/activity_detail.html"
    module_key = "activities"
    page_title = "Activité"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response

    def get_activity(self):
        activity = activity_for_console(self.space_console, self.kwargs["activity_id"])
        if activity is None:
            raise PermissionDenied("Cette Activity ne fait pas partie de votre portée autorisée.")
        return activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity
        context["console_page_title"] = activity.title
        context["can_manage_activity"] = can(self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity)
        context["can_view_requests"] = can(self.request.user, PermissionCode.ACTIVITY_REQUESTS_VIEW, activity=activity)
        context["can_view_access"] = can(self.request.user, PermissionCode.ACTIVITY_ACCESS_VIEW, activity=activity)
        context["can_view_commerce"] = (
            can(self.request.user, PermissionCode.ACTIVITY_COMMERCE_VIEW, activity=activity)
            or PermissionCode.ORDERS_VIEW in self.space_console.space_permissions
        )
        context["can_view_capacity"] = (
            can(self.request.user, PermissionCode.ACTIVITY_CAPACITY_VIEW, activity=activity)
            or PermissionCode.SPACE_ACTIVITIES_VIEW in self.space_console.space_permissions
        )
        context["requests"] = requests_for_console(self.space_console).filter(journey__activity=activity)[:8]
        context["accesses"] = accesses_for_console(self.space_console).filter(activity=activity)[:8]
        context["offers"] = offers_for_console(self.space_console).filter(activity=activity)[:8]
        context["capacity_pools"] = [pool for pool in capacity_for_console(self.space_console) if pool.activity_id == activity.pk][:8]
        context["orders"] = orders_for_console(self.space_console).filter(journey__activity=activity)[:8]
        return context


class SpaceConsoleCreateEventView(SpaceConsoleMixin, FormView):
    template_name = "events/event_form.html"
    form_class = EventForm
    module_key = "activities"
    page_title = "Créer un événement"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not self.space_console.can_manage_activities:
            raise PermissionDenied("Vous ne pouvez pas créer d'Activity dans cet Espace.")
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["organization"].queryset = Organization.objects.filter(pk=self.space.pk)
        form.fields["organization"].initial = self.space
        form.fields["organization"].widget.attrs["readonly"] = True
        return form

    def form_valid(self, form):
        if form.cleaned_data["organization"].pk != self.space.pk:
            form.add_error("organization", "L'événement doit appartenir à l'Espace courant.")
            return self.form_invalid(form)
        event = create_event(actor=self.request.user, **form.cleaned_data)
        ensure_policy(event)
        messages.success(self.request, "Événement créé dans cet Espace.")
        return redirect("organizations:console-activity-detail", slug=self.space.slug, activity_id=event.activity_id)


class SpaceConsoleRequestsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/requests.html"
    module_key = "requests"
    page_title = "Demandes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = requests_for_console(self.space_console)
        status = (self.request.GET.get("status") or "pending").strip()
        activity_id = (self.request.GET.get("activity") or "").strip()
        q = (self.request.GET.get("q") or "").strip()
        if status and status != "all":
            queryset = queryset.filter(status=status)
        if activity_id:
            queryset = queryset.filter(journey__activity_id=activity_id)
        if q:
            queryset = queryset.filter(
                Q(requester__email__icontains=q)
                | Q(journey__beneficiary__email__icontains=q)
                | Q(message__icontains=q)
            )
        context["page_obj"] = self.paginate(queryset)
        context["activities"] = activities_for_console(self.space_console)
        context["status_filter"] = status
        context["activity_filter"] = activity_id
        context["query"] = q
        return context


class SpaceRequestDecisionView(SpaceConsoleMixin, View):
    module_key = "requests"
    decision = None

    def post(self, request, *args, **kwargs):
        journey_request = get_object_or_404(requests_for_console(self.space_console), pk=kwargs["request_id"])
        if not can(request.user, PermissionCode.ACTIVITY_REQUESTS_DECIDE, activity=journey_request.journey.activity):
            raise PermissionDenied("Vous ne pouvez pas décider cette Demande.")
        comment = (request.POST.get("comment") or "").strip()
        try:
            if self.decision == "approve":
                approve_request(request=journey_request, actor=request.user, comment=comment)
                messages.success(request, "Demande approuvée.")
            else:
                reject_request(request=journey_request, actor=request.user, comment=comment)
                messages.success(request, "Demande refusée.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("organizations:console-requests", slug=self.space.slug)


class SpaceRequestApproveView(SpaceRequestDecisionView):
    decision = "approve"


class SpaceRequestRejectView(SpaceRequestDecisionView):
    decision = "reject"


class SpaceConsoleAccessView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/access.html"
    module_key = "access"
    page_title = "Accès"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = accesses_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        activity_id = (self.request.GET.get("activity") or "").strip()
        q = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)
        if q:
            queryset = queryset.filter(
                Q(beneficiary__email__icontains=q)
                | Q(beneficiary__username__icontains=q)
                | Q(activity__title__icontains=q)
            )
        context["page_obj"] = self.paginate(queryset)
        context["activities"] = activities_for_console(self.space_console)
        context["status_filter"] = status
        context["activity_filter"] = activity_id
        context["query"] = q
        return context


class SpaceAccessRevokeView(SpaceConsoleMixin, View):
    module_key = "access"

    def post(self, request, *args, **kwargs):
        access = get_object_or_404(accesses_for_console(self.space_console), pk=kwargs["access_id"])
        try:
            revoke_access(access=access, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Accès révoqué.")
        return redirect("organizations:console-access", slug=self.space.slug)


class SpaceConsoleOffersView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/offers.html"
    module_key = "offers"
    page_title = "Offres / Tarifs"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["offers"] = offers_for_console(self.space_console)
        context["capacity_pools"] = capacity_for_console(self.space_console)
        context["activities"] = activities_for_console(self.space_console)
        return context


class SpaceConsoleOrdersView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/orders.html"
    module_key = "orders"
    page_title = "Commandes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = orders_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        q = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if q:
            queryset = queryset.filter(
                Q(reference__icontains=q)
                | Q(buyer__email__icontains=q)
                | Q(journey__activity__title__icontains=q)
            )
        context["page_obj"] = self.paginate(queryset)
        context["status_filter"] = status
        context["query"] = q
        return context


class SpaceConsolePaymentsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/payments.html"
    module_key = "payments"
    page_title = "Paiements"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = payments_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        q = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if q:
            queryset = queryset.filter(Q(reference__icontains=q) | Q(commerce_order__reference__icontains=q))
        context["page_obj"] = self.paginate(queryset)
        context["status_filter"] = status
        context["query"] = q
        return context


class SpaceConsoleTeamView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/team.html"
    module_key = "team"
    page_title = "Équipe"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = team_for_console(self.space_console)
        context["can_manage_team"] = self.space_console.can_manage_team
        return context


class SpaceConsoleGroupsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/groups.html"
    module_key = "groups"
    page_title = "Groupes"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_obj"] = self.paginate(groups_for_console(self.space_console))
        return context


class SpaceConsolePlacesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/places.html"
    module_key = "places"
    page_title = "Lieux"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["places"] = places_for_console(self.space_console)
        context["can_manage_places"] = PermissionCode.SPACE_PLACES_MANAGE in self.space_console.space_permissions
        return context


class SpaceConsoleCRMView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/crm.html"
    module_key = "crm"
    page_title = "CRM"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = contacts_for_console(self.space_console)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        context["page_obj"] = self.paginate(queryset, per_page=40)
        context["query"] = q
        return context


class SpaceConsoleAudiencesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/audiences.html"
    module_key = "audiences"
    page_title = "Audiences"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_obj"] = self.paginate(audiences_for_console(self.space_console))
        return context


class SpaceConsolePromotionsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/promotions.html"
    module_key = "promotions"
    page_title = "Promotions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_obj"] = self.paginate(promotions_for_console(self.space_console))
        return context


class SpaceConsoleControlView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/control.html"
    module_key = "control"
    page_title = "Contrôle d’accès"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activities"] = [
            activity
            for activity in activities_for_console(self.space_console)
            if can(self.request.user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=activity)
            or can(self.request.user, PermissionCode.ACTIVITY_ACCESS_MANAGE, activity=activity)
        ]
        return context


class SpaceConsoleOperationsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/operations.html"
    module_key = "operations"
    page_title = "Opérations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = incidents_for_console(self.space_console)
        status = (self.request.GET.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        context["page_obj"] = self.paginate(queryset)
        context["status_filter"] = status
        return context


class SpaceConsoleAnalyticsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/analytics.html"
    module_key = "analytics"
    page_title = "Analyses"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["analytics"] = analytics_summary(self.space_console)
        return context


class SpaceConsoleAutomationView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/automation.html"
    module_key = "automation"
    page_title = "Automatisations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_obj"] = self.paginate(automation_rules_for_console(self.space_console))
        return context


class SpaceConsoleSettingsView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/settings.html"
    module_key = "settings"
    page_title = "Paramètres de l’Espace"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = self.space_console.can_manage_space
        return context

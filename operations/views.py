from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import (
    EventModerationForm,
    OperationsIncidentCreateForm,
    OperationsIncidentUpdateForm,
    OrganizationReviewForm,
)
from .models import ModerationStatus
from .permissions import user_can_access_operations
from .selectors import (
    get_moderation_cases,
    get_operations_events,
    get_operations_incidents,
    get_operations_organizations,
)
from .services import (
    build_operations_overview,
    change_organization_verification,
    create_incident,
    moderate_event,
    update_incident,
)


class StaffOperationsMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "accounts:login"
    raise_exception = True

    def test_func(self):
        return user_can_access_operations(self.request.user)


class OperationsDashboardView(StaffOperationsMixin, TemplateView):
    template_name = "operations/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["operations"] = build_operations_overview(self.request.user)
        return context


class OperationsOrganizationsView(StaffOperationsMixin, TemplateView):
    template_name = "operations/organizations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = get_operations_organizations(self.request.user)
        status = (self.request.GET.get("status") or "").strip()
        query = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(verification_status=status)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        context["organizations"] = queryset[:100]
        context["selected_status"] = status
        context["query"] = query
        context["review_form"] = OrganizationReviewForm()
        return context


class OrganizationReviewView(StaffOperationsMixin, View):
    def post(self, request, pk):
        organization = get_object_or_404(get_operations_organizations(request.user), pk=pk)
        form = OrganizationReviewForm(request.POST)
        if form.is_valid():
            change_organization_verification(
                organization=organization,
                status=form.cleaned_data["status"],
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, f"Statut Operations mis à jour pour {organization.name}.")
        else:
            messages.error(request, "La décision de modération est incomplète.")
        return redirect("operations:organizations")


class OperationsEventsView(StaffOperationsMixin, TemplateView):
    template_name = "operations/events.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = get_operations_events(self.request.user)
        status = (self.request.GET.get("status") or "").strip()
        query = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(slug__icontains=query)
                | Q(organization__name__icontains=query)
            )
        context["events"] = queryset[:100]
        context["selected_status"] = status
        context["query"] = query
        context["moderation_form"] = EventModerationForm()
        return context


class EventModerationView(StaffOperationsMixin, View):
    def post(self, request, pk):
        event = get_object_or_404(get_operations_events(request.user), pk=pk)
        form = EventModerationForm(request.POST)
        if form.is_valid():
            moderate_event(
                event=event,
                action=form.cleaned_data["action"],
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, f"Action Operations appliquée à {event.title}.")
        else:
            messages.error(request, "L'action de modération est incomplète.")
        return redirect("operations:events")


class OperationsIncidentsView(StaffOperationsMixin, TemplateView):
    template_name = "operations/incidents.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = get_operations_incidents(self.request.user)
        status = (self.request.GET.get("status") or "").strip()
        severity = (self.request.GET.get("severity") or "").strip()
        query = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if severity:
            queryset = queryset.filter(severity=severity)
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query))
        context["incidents"] = queryset[:100]
        context["selected_status"] = status
        context["selected_severity"] = severity
        context["query"] = query
        return context


class OperationsIncidentCreateView(StaffOperationsMixin, FormView):
    template_name = "operations/incident_form.html"
    form_class = OperationsIncidentCreateForm

    def form_valid(self, form):
        create_incident(actor=self.request.user, **form.cleaned_data)
        messages.success(self.request, "Incident Operations créé.")
        return redirect("operations:incidents")


class OperationsIncidentDetailView(StaffOperationsMixin, TemplateView):
    template_name = "operations/incident_detail.html"

    def _incident(self):
        return get_object_or_404(get_operations_incidents(self.request.user), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incident = self._incident()
        context["incident"] = incident
        context["form"] = OperationsIncidentUpdateForm(instance=incident)
        return context

    def post(self, request, *args, **kwargs):
        incident = self._incident()
        form = OperationsIncidentUpdateForm(request.POST, instance=incident)
        if form.is_valid():
            update_incident(
                incident=incident,
                actor=request.user,
                status=form.cleaned_data["status"],
                severity=form.cleaned_data["severity"],
                assigned_to=form.cleaned_data["assigned_to"],
                resolution=form.cleaned_data["resolution"],
            )
            messages.success(request, "Incident Operations mis à jour.")
            return redirect("operations:incident-detail", pk=incident.pk)
        return self.render_to_response({"incident": incident, "form": form}, status=400)


class ModerationQueueView(StaffOperationsMixin, TemplateView):
    template_name = "operations/moderation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = get_moderation_cases(self.request.user)
        status = (self.request.GET.get("status") or "").strip()
        if status:
            queryset = queryset.filter(status=status)
        else:
            queryset = queryset.filter(status__in=[ModerationStatus.OPEN, ModerationStatus.REVIEWING])
        context["cases"] = queryset[:100]
        context["selected_status"] = status
        return context

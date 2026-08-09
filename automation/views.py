from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from crm.permissions import user_can_manage_crm, user_can_view_crm
from events.models import Event
from events.permissions import user_can_manage_event
from organizations.models import Organization

from .forms import CRMWorkflowActionForm, CRMWorkflowForm, EventAutomationPolicyForm
from .models import CRMWorkflow, CRMWorkflowAction
from .services import ensure_policy


class EventAutomationPolicyView(LoginRequiredMixin, UpdateView):
    form_class = EventAutomationPolicyForm
    template_name = "automation/event_policy.html"
    context_object_name = "policy"

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event.objects.select_related("organization", "organizer"), slug=kwargs["slug"])
        if not user_can_manage_event(request.user, self.event):
            raise PermissionDenied("Vous ne pouvez pas configurer cet événement.")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return ensure_policy(self.event)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["recent_runs"] = self.event.automation_runs.all()[:20]
        return context

    def form_valid(self, form):
        messages.success(self.request, "Makolo Autopilot a été configuré pour cet événement.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("automation:event-policy", kwargs={"slug": self.event.slug})


class CRMWorkflowListView(LoginRequiredMixin, TemplateView):
    template_name = "automation/crm_workflows.html"
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_view_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas accès aux automatisations CRM de cette organisation.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self._organization()
        workflows = CRMWorkflow.objects.filter(organization=organization).select_related("event", "segment", "ticket_type").prefetch_related("actions")
        context.update(
            {
                "organization": organization,
                "workflows": workflows,
                "can_manage": user_can_manage_crm(self.request.user, organization),
                "active_count": workflows.filter(is_active=True).count(),
                "runs_count": sum(workflow.runs.count() for workflow in workflows),
            }
        )
        return context


class CRMWorkflowCreateView(LoginRequiredMixin, FormView):
    template_name = "automation/crm_workflow_form.html"
    form_class = CRMWorkflowForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        if not user_can_manage_crm(request.user, self.organization):
            raise PermissionDenied("Vous ne pouvez pas créer de scénario CRM pour cette organisation.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self.organization, "workflow": None})
        return context

    def form_valid(self, form):
        workflow = form.save(commit=False)
        workflow.organization = self.organization
        workflow.created_by = self.request.user
        workflow.full_clean()
        workflow.save()
        messages.success(self.request, "Scénario CRM créé. Ajoutez maintenant ses actions.")
        return redirect("automation:crm-workflow-detail", pk=workflow.pk)


class CRMWorkflowUpdateView(LoginRequiredMixin, UpdateView):
    model = CRMWorkflow
    form_class = CRMWorkflowForm
    template_name = "automation/crm_workflow_form.html"
    context_object_name = "workflow"
    login_url = "core:login"

    def get_queryset(self):
        return CRMWorkflow.objects.select_related("organization", "event", "segment", "ticket_type")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not user_can_manage_crm(request.user, self.object.organization):
            raise PermissionDenied("Vous ne pouvez pas modifier ce scénario CRM.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.object.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.object.organization
        return context

    def form_valid(self, form):
        messages.success(self.request, "Scénario CRM mis à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("automation:crm-workflow-detail", kwargs={"pk": self.object.pk})


class CRMWorkflowDetailView(LoginRequiredMixin, TemplateView):
    template_name = "automation/crm_workflow_detail.html"
    login_url = "core:login"

    def _workflow(self):
        workflow = get_object_or_404(
            CRMWorkflow.objects.select_related("organization", "event", "segment", "ticket_type", "created_by"),
            pk=self.kwargs["pk"],
        )
        if not user_can_view_crm(self.request.user, workflow.organization):
            raise PermissionDenied("Vous n’avez pas accès à ce scénario CRM.")
        return workflow

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workflow = self._workflow()
        context.update(
            {
                "workflow": workflow,
                "organization": workflow.organization,
                "actions": workflow.actions.select_related("template", "tag").all(),
                "recent_runs": workflow.runs.select_related("contact", "event", "order").prefetch_related("action_runs__action")[:40],
                "can_manage": user_can_manage_crm(self.request.user, workflow.organization),
                "action_form": CRMWorkflowActionForm(workflow=workflow),
            }
        )
        return context


class CRMWorkflowActionCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous ne pouvez pas modifier les actions de ce scénario.")
        form = CRMWorkflowActionForm(request.POST, workflow=workflow)
        if form.is_valid():
            action = form.save(commit=False)
            action.workflow = workflow
            action.full_clean()
            action.save()
            messages.success(request, "Action ajoutée au scénario.")
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
        return redirect("automation:crm-workflow-detail", pk=workflow.pk)


class CRMWorkflowToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous ne pouvez pas activer ou suspendre ce scénario.")
        workflow.is_active = not workflow.is_active
        workflow.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Scénario activé." if workflow.is_active else "Scénario mis en pause.")
        return redirect("automation:crm-workflow-detail", pk=workflow.pk)


class CRMWorkflowActionToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, action_id):
        workflow = get_object_or_404(CRMWorkflow.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, workflow.organization):
            raise PermissionDenied("Vous ne pouvez pas modifier cette action.")
        action = get_object_or_404(CRMWorkflowAction, pk=action_id, workflow=workflow)
        action.is_active = not action.is_active
        action.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Action activée." if action.is_active else "Action désactivée.")
        return redirect("automation:crm-workflow-detail", pk=workflow.pk)

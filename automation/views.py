from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import UpdateView

from events.models import Event
from events.permissions import user_can_manage_event

from .forms import EventAutomationPolicyForm
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

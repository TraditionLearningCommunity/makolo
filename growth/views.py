from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from events.models import Event

from .forms import EventFeedbackForm, MarketingLinkForm
from .models import EventFeedback, MarketingLink
from .permissions import (
    get_growth_organizations,
    user_can_manage_growth_acquisition,
    user_can_view_private_feedback,
)
from .services import (
    activate_crm_preset,
    available_crm_presets,
    build_growth_v1_dashboard,
    can_submit_feedback,
    capture_marketing_link,
    submit_event_feedback,
)


class GrowthDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "growth/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organizations = list(get_growth_organizations(self.request.user)[:50])
        context["organizations"] = organizations
        context["cards"] = [build_growth_v1_dashboard(org, self.request.user) for org in organizations]
        return context


class OrganizationGrowthView(LoginRequiredMixin, TemplateView):
    template_name = "growth/organization.html"
    login_url = "core:login"

    def _organization(self):
        return get_object_or_404(get_growth_organizations(self.request.user), slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self._organization()
        context["organization"] = organization
        context["growth"] = build_growth_v1_dashboard(organization, self.request.user)
        context["can_manage"] = user_can_manage_growth_acquisition(self.request.user, organization)
        context["can_view_feedback"] = user_can_view_private_feedback(self.request.user, organization)
        context["presets"] = available_crm_presets(organization)
        context["events"] = Event.objects.filter(organization=organization).order_by("-start_at")[:100]
        return context


class MarketingLinkCreateView(LoginRequiredMixin, View):
    template_name = "growth/link_form.html"
    login_url = "core:login"

    def _organization(self, request, slug):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        if not user_can_manage_growth_acquisition(request.user, organization):
            raise PermissionDenied("Un rôle Owner, Admin ou Marketing est requis.")
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        return render(request, self.template_name, {"organization": organization, "form": MarketingLinkForm(organization=organization)})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        form = MarketingLinkForm(request.POST, organization=organization)
        if form.is_valid():
            link = form.save(commit=False)
            link.organization = organization
            link.created_by = request.user
            link.full_clean()
            link.save()
            messages.success(request, f"Lien marketing créé : {link.code}.")
            return redirect("growth:organization", slug=organization.slug)
        return render(request, self.template_name, {"organization": organization, "form": form}, status=400)


class MarketingLinkToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        link = get_object_or_404(MarketingLink.objects.select_related("organization"), pk=pk)
        if not user_can_manage_growth_acquisition(request.user, link.organization):
            raise PermissionDenied
        link.is_active = not link.is_active
        link.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Lien marketing activé." if link.is_active else "Lien marketing mis en pause.")
        return redirect("growth:organization", slug=link.organization.slug)


class MarketingLinkQrView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, pk):
        link = get_object_or_404(MarketingLink.objects.select_related("organization"), pk=pk)
        if not user_can_manage_growth_acquisition(request.user, link.organization):
            raise PermissionDenied
        short_url = request.build_absolute_uri(reverse("growth_public:redirect", kwargs={"code": link.code}))
        image = qrcode.make(short_url)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type="image/png")


class EventFeedbackSubmitView(LoginRequiredMixin, View):
    template_name = "growth/feedback_form.html"
    login_url = "core:login"

    def _event(self, request, slug):
        event = get_object_or_404(Event.objects.select_related("organization"), slug=slug)
        if not can_submit_feedback(request.user, event):
            raise PermissionDenied("Le feedback est disponible après l'événement pour les participants confirmés.")
        return event

    def get(self, request, slug):
        event = self._event(request, slug)
        existing = EventFeedback.objects.filter(event=event, user=request.user).first()
        form = EventFeedbackForm(instance=existing)
        return render(request, self.template_name, {"event": event, "form": form})

    def post(self, request, slug):
        event = self._event(request, slug)
        existing = EventFeedback.objects.filter(event=event, user=request.user).first()
        form = EventFeedbackForm(request.POST, instance=existing)
        if form.is_valid():
            submit_event_feedback(
                user=request.user,
                event=event,
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data.get("comment", ""),
            )
            messages.success(request, "Merci. Votre feedback privé a été transmis à l'organisateur.")
            return redirect("events:detail", slug=event.slug)
        return render(request, self.template_name, {"event": event, "form": form}, status=400)


class OrganizationFeedbackView(LoginRequiredMixin, TemplateView):
    template_name = "growth/feedback_list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = get_object_or_404(get_growth_organizations(self.request.user), slug=self.kwargs["slug"])
        if not user_can_view_private_feedback(self.request.user, organization):
            raise PermissionDenied
        context["organization"] = organization
        context["feedback"] = EventFeedback.objects.filter(event__organization=organization).select_related(
            "event", "user"
        )[:200]
        return context


class CRMPresetActivateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug, preset_key):
        organization = get_object_or_404(get_growth_organizations(request.user), slug=slug)
        if not user_can_manage_growth_acquisition(request.user, organization):
            raise PermissionDenied
        event = None
        event_id = (request.POST.get("event_id") or "").strip()
        if event_id:
            event = get_object_or_404(Event.objects.filter(organization=organization), pk=event_id)
        try:
            workflow, created = activate_crm_preset(
                organization=organization,
                actor=request.user,
                preset_key=preset_key,
                event=event,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(
                request,
                f"Preset activé : {workflow.name}." if created else f"Preset déjà présent et actif : {workflow.name}.",
            )
        return redirect("growth:organization", slug=organization.slug)

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import FormView, TemplateView

from organizations.models import Organization

from .audience_forms import AudienceCreateForm
from .audiences import (
    archive_audience,
    create_audience_from_group,
    create_audience_from_snapshot,
    create_static_audience,
)
from .canonical_models import Audience
from .canonical_selectors import audience_members, audiences_for_space
from .permissions import user_can_manage_crm, user_can_view_crm


class AudienceListView(LoginRequiredMixin, TemplateView):
    template_name = "crm/audience_list.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_view_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas accès aux Audiences de cet Espace.")
        context.update(
            {
                "organization": organization,
                "audiences": audiences_for_space(organization, include_archived=True),
                "can_manage": user_can_manage_crm(self.request.user, organization),
            }
        )
        return context


class AudienceCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/audience_form.html"
    form_class = AudienceCreateForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        if not user_can_manage_crm(request.user, self.organization):
            raise PermissionDenied("Vous ne pouvez pas gérer les Audiences de cet Espace.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.organization
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        common = {
            "organization": self.organization,
            "name": data["name"],
            "description": data.get("description", ""),
            "created_by": self.request.user,
        }
        if data["source"] == AudienceCreateForm.SOURCE_GROUP:
            audience = create_audience_from_group(group=data["group"], **common)
        elif data["source"] == AudienceCreateForm.SOURCE_SNAPSHOT:
            audience = create_audience_from_snapshot(snapshot=data["snapshot"], **common)
        else:
            audience = create_static_audience(profiles=data.get("profiles") or (), **common)
        messages.success(self.request, "Audience créée. Son appartenance ne modifie aucun consentement marketing.")
        return redirect("crm:audience-detail", pk=audience.pk)


class AudienceDetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/audience_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audience = get_object_or_404(Audience.objects.select_related("organization", "source_group", "source_snapshot"), pk=self.kwargs["pk"])
        if not user_can_view_crm(self.request.user, audience.organization):
            raise PermissionDenied("Vous n’avez pas accès à cette Audience.")
        context.update(
            {
                "audience": audience,
                "organization": audience.organization,
                "members": audience_members(audience),
                "can_manage": user_can_manage_crm(self.request.user, audience.organization),
            }
        )
        return context


class AudienceArchiveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        audience = get_object_or_404(Audience.objects.select_related("organization"), pk=pk)
        archive_audience(audience=audience, actor=request.user)
        messages.success(request, "Audience archivée.")
        return redirect("crm:audience-detail", pk=audience.pk)

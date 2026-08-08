from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import OrganizationForm, OrganizationMemberForm
from .models import Organization, OrganizationMembership
from .permissions import user_can_manage_organization, user_can_view_organization
from .services import add_or_update_member, create_organization, deactivate_member, find_user_for_team


class OrganizationListView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = "organizations/list.html"
    context_object_name = "organizations"

    def get_queryset(self):
        if self.request.user.is_staff:
            return Organization.objects.all()
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
        ).distinct()


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    form_class = OrganizationForm
    template_name = "organizations/form.html"

    def form_valid(self, form):
        self.object = create_organization(
            creator=self.request.user,
            name=form.cleaned_data["name"],
            description=form.cleaned_data.get("description", ""),
            website=form.cleaned_data.get("website", ""),
            contact_email=form.cleaned_data.get("contact_email", ""),
            contact_phone=form.cleaned_data.get("contact_phone", ""),
            country=form.cleaned_data.get("country", ""),
            city=form.cleaned_data.get("city", ""),
            public_profile=form.cleaned_data.get("public_profile", True),
        )
        messages.success(self.request, "Organisation créée. Vous en êtes propriétaire.")
        return redirect("organizations:detail", slug=self.object.slug)


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = "organizations/detail.html"
    context_object_name = "organization"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not user_can_view_organization(self.request.user, obj):
            raise PermissionDenied("Cette organisation n'est pas accessible.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = self.object.memberships.select_related("user").filter(is_active=True)
        context["events"] = self.object.events.order_by("-created_at")[:20]
        context["can_manage"] = user_can_manage_organization(self.request.user, self.object)
        return context


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "organizations/form.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not user_can_manage_organization(request.user, self.object):
            raise PermissionDenied("Vous ne pouvez pas modifier cette organisation.")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, "Organisation mise à jour.")
        return reverse("organizations:detail", kwargs={"slug": self.object.slug})


class OrganizationMemberCreateView(LoginRequiredMixin, View):
    def get(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_organization(request.user, organization):
            raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
        from django.shortcuts import render

        return render(
            request,
            "organizations/member_form.html",
            {"organization": organization, "form": OrganizationMemberForm()},
        )

    def post(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_organization(request.user, organization):
            raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
        form = OrganizationMemberForm(request.POST)
        if form.is_valid():
            try:
                user = find_user_for_team(email=form.cleaned_data["email"])
                add_or_update_member(
                    organization=organization,
                    actor=request.user,
                    user=user,
                    role=form.cleaned_data["role"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Membre ajouté ou mis à jour.")
                return redirect("organizations:detail", slug=organization.slug)
        from django.shortcuts import render

        return render(request, "organizations/member_form.html", {"organization": organization, "form": form})


class OrganizationMemberDeactivateView(LoginRequiredMixin, View):
    def post(self, request, slug, pk):
        organization = get_object_or_404(Organization, slug=slug)
        membership = get_object_or_404(OrganizationMembership, pk=pk, organization=organization)
        try:
            deactivate_member(membership=membership, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Membre désactivé.")
        return redirect("organizations:detail", slug=organization.slug)

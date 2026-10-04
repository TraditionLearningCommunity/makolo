from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, RedirectView, UpdateView

from .console_context import authorized_spaces
from .forms import OrganizationFollowPreferenceForm, OrganizationForm, OrganizationMemberForm
from .models import Organization, OrganizationFollow, OrganizationVerificationStatus, SpaceLifecycle, TeamMembership
from .permissions import user_can_manage_organization, user_can_manage_organization_team
from .services import (
    add_or_update_member,
    create_organization,
    deactivate_member,
    find_user_for_team,
    follow_organization,
    unfollow_organization,
    update_follow_preferences,
    update_organization,
)


class OrganizationListView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = "organizations/list.html"
    context_object_name = "organizations"

    def get_queryset(self):
        return authorized_spaces(self.request.user)


class FollowingListView(LoginRequiredMixin, ListView):
    model = OrganizationFollow
    template_name = "organizations/following_list.html"
    context_object_name = "follows"
    paginate_by = 30

    def get_queryset(self):
        return OrganizationFollow.objects.filter(user=self.request.user).select_related("organization")


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    form_class = OrganizationForm
    template_name = "organizations/form.html"

    def form_valid(self, form):
        self.object = create_organization(
            creator=self.request.user,
            name=form.cleaned_data["name"],
            archetype=form.cleaned_data["archetype"],
            description=form.cleaned_data.get("description", ""),
            website=form.cleaned_data.get("website", ""),
            contact_email=form.cleaned_data.get("contact_email", ""),
            contact_phone=form.cleaned_data.get("contact_phone", ""),
            country=form.cleaned_data.get("country", ""),
            city=form.cleaned_data.get("city", ""),
            public_profile=form.cleaned_data.get("public_profile", True),
            searchable=form.cleaned_data.get("searchable", True),
        )
        messages.success(self.request, "Espace créé. Vous en êtes propriétaire.")
        return redirect("organizations:console-overview", slug=self.object.slug)


class PublicOrganizationDetailView(RedirectView):
    """Compatibility entry point redirecting to the canonical public Space Passeport."""

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        organization = get_object_or_404(
            Organization.objects.filter(
                public_profile=True,
                searchable=True,
                lifecycle=SpaceLifecycle.ACTIVE,
            ),
            slug=self.kwargs["slug"],
        )
        return reverse("public-passport", kwargs={"identifier": organization.slug})


class OrganizationFollowToggleView(LoginRequiredMixin, View):
    def post(self, request, slug):
        organization = get_object_or_404(
            Organization.objects.filter(
                public_profile=True,
                searchable=True,
                lifecycle=SpaceLifecycle.ACTIVE,
            ),
            slug=slug,
        )
        follow = OrganizationFollow.objects.filter(organization=organization, user=request.user).first()
        if follow:
            unfollow_organization(follow=follow, user=request.user)
            messages.success(request, f"Vous ne suivez plus {organization.name}.")
        else:
            follow_organization(user=request.user, organization=organization)
            messages.success(request, f"Vous suivez maintenant {organization.name}.")
        return redirect("organizer_public:detail", slug=organization.slug)


class OrganizationFollowPreferencesView(LoginRequiredMixin, View):
    template_name = "organizations/follow_preferences.html"

    def _follow(self, request, slug):
        return get_object_or_404(
            OrganizationFollow.objects.select_related("organization"),
            organization__slug=slug,
            user=request.user,
        )

    def get(self, request, slug):
        follow = self._follow(request, slug)
        return render(
            request,
            self.template_name,
            {
                "follow": follow,
                "organization": follow.organization,
                "form": OrganizationFollowPreferenceForm(instance=follow),
            },
        )

    def post(self, request, slug):
        follow = self._follow(request, slug)
        form = OrganizationFollowPreferenceForm(request.POST, instance=follow)
        if form.is_valid():
            update_follow_preferences(
                follow=follow,
                user=request.user,
                **{name: form.cleaned_data[name] for name in form.Meta.fields},
            )
            messages.success(request, "Préférences de cet Espace mises à jour.")
            return redirect("organizer_public:detail", slug=follow.organization.slug)
        return render(
            request,
            self.template_name,
            {"follow": follow, "organization": follow.organization, "form": form},
            status=400,
        )


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "organizations/form.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not user_can_manage_organization(request.user, self.object):
            raise PermissionDenied("Vous ne pouvez pas modifier cet Espace.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            self.object = update_organization(
                organization=self.object,
                actor=self.request.user,
                **{name: form.cleaned_data[name] for name in form.Meta.fields},
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            return self.form_invalid(form)
        return redirect(self.get_success_url())

    def get_success_url(self):
        messages.success(self.request, "Espace mis à jour.")
        return reverse("organizations:console-settings", kwargs={"slug": self.object.slug})


class OrganizationMemberCreateView(LoginRequiredMixin, View):
    def get(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_organization_team(request.user, organization):
            raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
        return render(
            request,
            "organizations/member_form.html",
            {"organization": organization, "space": organization, "form": OrganizationMemberForm()},
        )

    def post(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_organization_team(request.user, organization):
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
                messages.success(request, "Membre et responsabilité mis à jour.")
                return redirect("organizations:console-team", slug=organization.slug)
        return render(
            request,
            "organizations/member_form.html",
            {"organization": organization, "space": organization, "form": form},
        )


class OrganizationMemberDeactivateView(LoginRequiredMixin, View):
    def post(self, request, slug, pk):
        organization = get_object_or_404(Organization, slug=slug)
        membership = get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=pk,
            team__organization=organization,
        )
        try:
            deactivate_member(membership=membership, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Membre retiré de l'équipe.")
        return redirect("organizations:console-team", slug=organization.slug)

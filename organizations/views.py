from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from events.models import EventStatus, EventVisibility

from .forms import OrganizationFollowPreferenceForm, OrganizationForm, OrganizationMemberForm
from .models import (
    Organization,
    OrganizationFollow,
    OrganizationMembership,
    OrganizationVerificationStatus,
)
from .permissions import (
    user_can_access_organization_workspace,
    user_can_manage_organization,
)
from .services import (
    add_or_update_member,
    create_organization,
    deactivate_member,
    find_user_for_team,
    follow_organization,
    unfollow_organization,
    update_follow_preferences,
)


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


class PublicOrganizationDetailView(DetailView):
    model = Organization
    template_name = "organizations/public_detail.html"
    context_object_name = "organization"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Organization.objects.filter(public_profile=True).exclude(
            verification_status=OrganizationVerificationStatus.SUSPENDED
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["events"] = self.object.events.filter(
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
        ).select_related("venue", "category").order_by("start_at")[:24]
        context["is_verified"] = self.object.verification_status == OrganizationVerificationStatus.VERIFIED
        context["follower_count"] = self.object.followers.count()
        context["follow"] = None
        if self.request.user.is_authenticated:
            context["follow"] = OrganizationFollow.objects.filter(
                organization=self.object,
                user=self.request.user,
            ).first()
        return context


class OrganizationFollowToggleView(LoginRequiredMixin, View):
    def post(self, request, slug):
        organization = get_object_or_404(
            Organization.objects.filter(public_profile=True).exclude(
                verification_status=OrganizationVerificationStatus.SUSPENDED
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
        return render(request, self.template_name, {"follow": follow, "organization": follow.organization, "form": OrganizationFollowPreferenceForm(instance=follow)})

    def post(self, request, slug):
        follow = self._follow(request, slug)
        form = OrganizationFollowPreferenceForm(request.POST, instance=follow)
        if form.is_valid():
            update_follow_preferences(
                follow=follow,
                user=request.user,
                **{name: form.cleaned_data[name] for name in form.Meta.fields},
            )
            messages.success(request, "Préférences de cet organisateur mises à jour.")
            return redirect("organizer_public:detail", slug=follow.organization.slug)
        return render(request, self.template_name, {"follow": follow, "organization": follow.organization, "form": form}, status=400)


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = "organizations/detail.html"
    context_object_name = "organization"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not user_can_access_organization_workspace(self.request.user, obj):
            raise PermissionDenied("Cet espace d'équipe n'est accessible qu'aux membres de l'organisation.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["memberships"] = self.object.memberships.select_related("user").filter(is_active=True)
        context["events"] = self.object.events.order_by("-created_at")[:20]
        context["can_manage"] = user_can_manage_organization(self.request.user, self.object)
        context["follower_count"] = self.object.followers.count()
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
        return render(request, "organizations/member_form.html", {"organization": organization, "form": OrganizationMemberForm()})

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

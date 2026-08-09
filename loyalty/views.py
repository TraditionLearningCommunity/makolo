from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from organizations.models import Organization
from organizations.permissions import organization_has_public_profile

from .forms import LoyaltyProgramForm, LoyaltyRewardForm, LoyaltyTierForm, MembershipPlanForm, PointsAdjustmentForm
from .models import LoyaltyAccount, LoyaltyProgram, LoyaltyReward, LoyaltyTier, MembershipPlan, MembershipStatus, MembershipSubscription
from .permissions import user_can_manage_loyalty_finance, user_can_manage_loyalty_strategy, user_can_view_loyalty_workspace
from .selectors import get_accounts_visible_to, get_programs_visible_to, get_subscriptions_visible_to
from .services import activate_membership, adjust_points, cancel_membership, redeem_reward, request_membership


class LoyaltyDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "loyalty/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accounts"] = get_accounts_visible_to(self.request.user).filter(user=self.request.user).prefetch_related("program__rewards")
        context["subscriptions"] = get_subscriptions_visible_to(self.request.user).filter(user=self.request.user)[:20]
        context["managed_programs"] = get_programs_visible_to(self.request.user)
        return context


class OrganizationLoyaltyPortalView(TemplateView):
    template_name = "loyalty/portal.html"

    def dispatch(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        if not organization_has_public_profile(self.organization) and not (
            request.user.is_authenticated and user_can_view_loyalty_workspace(request.user, self.organization)
        ):
            raise PermissionDenied("Ce programme n'est pas public.")
        self.program = LoyaltyProgram.objects.filter(organization=self.organization, is_active=True).first()
        if not self.program:
            return redirect("organizations:public-detail", slug=self.organization.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.organization
        context["program"] = self.program
        context["plans"] = self.program.membership_plans.filter(is_active=True)
        context["rewards"] = self.program.rewards.filter(is_active=True)
        context["tiers"] = self.program.tiers.filter(is_active=True)
        if self.request.user.is_authenticated:
            context["account"] = LoyaltyAccount.objects.filter(program=self.program, user=self.request.user).select_related("current_tier").first()
            context["membership"] = MembershipSubscription.objects.filter(program=self.program, user=self.request.user, status__in=[MembershipStatus.PENDING, MembershipStatus.ACTIVE]).select_related("plan", "benefit_code").first()
        return context


class MembershipJoinView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        plan = get_object_or_404(MembershipPlan.objects.select_related("program__organization"), pk=pk)
        try:
            subscription = request_membership(user=request.user, plan=plan)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            if subscription.status == MembershipStatus.ACTIVE:
                messages.success(request, "Membership activé.")
            else:
                messages.success(request, "Demande enregistrée. Une validation Finance est requise pour ce plan payant.")
        return redirect("loyalty:portal", slug=plan.program.organization.slug)


class MembershipCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        subscription = get_object_or_404(get_subscriptions_visible_to(request.user), pk=pk)
        try:
            cancel_membership(subscription=subscription, actor=request.user)
            messages.success(request, "Membership annulé.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("loyalty:dashboard")


class RewardRedeemView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        reward = get_object_or_404(LoyaltyReward.objects.select_related("program__organization"), pk=pk, is_active=True)
        try:
            redemption = redeem_reward(user=request.user, reward=reward)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            if redemption.promotion_code_id:
                messages.success(request, f"Récompense obtenue. Code privé : {redemption.promotion_code.code}")
            else:
                messages.success(request, "Récompense obtenue. Consultez les instructions dans votre espace fidélité.")
        return redirect("loyalty:portal", slug=reward.program.organization.slug)


class LoyaltyWorkspaceView(LoginRequiredMixin, TemplateView):
    template_name = "loyalty/workspace.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        if not user_can_view_loyalty_workspace(request.user, self.organization):
            raise PermissionDenied("Vous n'avez pas accès à la fidélité de cette organisation.")
        self.program = LoyaltyProgram.objects.filter(organization=self.organization).first()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "organization": self.organization,
            "program": self.program,
            "can_strategy": user_can_manage_loyalty_strategy(self.request.user, self.organization),
            "can_finance": user_can_manage_loyalty_finance(self.request.user, self.organization),
        })
        if self.program:
            context["accounts"] = self.program.accounts.select_related("user", "current_tier").order_by("-lifetime_earned")[:100]
            context["subscriptions"] = self.program.subscriptions.select_related("user", "plan").order_by("-requested_at")[:100]
            context["tiers"] = self.program.tiers.all()
            context["plans"] = self.program.membership_plans.all()
            context["rewards"] = self.program.rewards.all()
        return context


class ProgramEditView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "loyalty/form.html"

    def get_org(self, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_loyalty_strategy(self.request.user, organization):
            raise PermissionDenied("Un rôle Marketing, Owner ou Admin est requis.")
        return organization

    def get(self, request, slug):
        from django.shortcuts import render
        organization = self.get_org(slug)
        instance = LoyaltyProgram.objects.filter(organization=organization).first()
        return render(request, self.template_name, {"form": LoyaltyProgramForm(instance=instance), "title": "Programme fidélité", "organization": organization})

    def post(self, request, slug):
        organization = self.get_org(slug)
        instance = LoyaltyProgram.objects.filter(organization=organization).first()
        form = LoyaltyProgramForm(request.POST, instance=instance)
        if form.is_valid():
            program = form.save(commit=False)
            program.organization = organization
            if not program.pk:
                program.created_by = request.user
            program.full_clean()
            program.save()
            messages.success(request, "Programme fidélité enregistré.")
            return redirect("loyalty:workspace", slug=slug)
        from django.shortcuts import render
        return render(request, self.template_name, {"form": form, "title": "Programme fidélité", "organization": organization})


class ProgramObjectEditView(LoginRequiredMixin, View):
    model = None
    form_class = None
    label = "Élément"
    login_url = "core:login"
    template_name = "loyalty/form.html"

    def setup_context(self, request, slug, pk=None):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_loyalty_strategy(request.user, organization):
            raise PermissionDenied("Un rôle Marketing, Owner ou Admin est requis.")
        program = get_object_or_404(LoyaltyProgram, organization=organization)
        instance = get_object_or_404(self.model, pk=pk, program=program) if pk else None
        return organization, program, instance

    def form(self, *args, organization, instance=None):
        kwargs = {"instance": instance}
        if self.form_class in {MembershipPlanForm, LoyaltyRewardForm}:
            kwargs["organization"] = organization
        return self.form_class(*args, **kwargs)

    def get(self, request, slug, pk=None):
        from django.shortcuts import render
        organization, program, instance = self.setup_context(request, slug, pk)
        return render(request, self.template_name, {"form": self.form(organization=organization, instance=instance), "title": self.label, "organization": organization})

    def post(self, request, slug, pk=None):
        from django.shortcuts import render
        organization, program, instance = self.setup_context(request, slug, pk)
        form = self.form(request.POST, organization=organization, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.program = program
            if hasattr(obj, "created_by_id") and not obj.created_by_id:
                obj.created_by = request.user
            obj.full_clean()
            obj.save()
            messages.success(request, f"{self.label} enregistré.")
            return redirect("loyalty:workspace", slug=slug)
        return render(request, self.template_name, {"form": form, "title": self.label, "organization": organization})


class TierEditView(ProgramObjectEditView):
    model = LoyaltyTier
    form_class = LoyaltyTierForm
    label = "Niveau fidélité"


class PlanEditView(ProgramObjectEditView):
    model = MembershipPlan
    form_class = MembershipPlanForm
    label = "Plan membership"


class RewardEditView(ProgramObjectEditView):
    model = LoyaltyReward
    form_class = LoyaltyRewardForm
    label = "Récompense"


class MembershipActivateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        subscription = get_object_or_404(get_subscriptions_visible_to(request.user), pk=pk)
        try:
            activate_membership(subscription=subscription, actor=request.user)
            messages.success(request, "Membership activé manuellement.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("loyalty:workspace", slug=subscription.program.organization.slug)


class AccountAdjustView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        account = get_object_or_404(get_accounts_visible_to(request.user), pk=pk)
        form = PointsAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                adjust_points(actor=request.user, account=account, **form.cleaned_data)
                messages.success(request, "Solde fidélité ajusté avec audit.")
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.error(request, "Ajustement invalide.")
        return redirect("loyalty:workspace", slug=account.program.organization.slug)

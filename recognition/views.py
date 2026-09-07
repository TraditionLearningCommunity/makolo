from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, View

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization

from .economy import redeem_reward
from .models import RewardDefinition
from .selectors import account_for_profile, account_for_space, active_rewards, compact_credits
from .services import get_or_create_account


class RecognitionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "recognition/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = account_for_profile(self.request.user)
        context.update({
            "recognition_subject": self.request.user,
            "recognition_subject_kind": "profile",
            "account": account,
            "credits_display": compact_credits(account.points_balance if account else 0),
            "ledger_entries": account.ledger_entries.all()[:30] if account else (),
            "achievements": account.achievement_grants.select_related("achievement").all() if account else (),
            "rewards": active_rewards(),
        })
        return context


class SpaceRecognitionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "recognition/dashboard.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.space = get_object_or_404(Organization, pk=kwargs["space_id"])
        if not can(request.user, PermissionCode.SPACE_RECOGNITION_VIEW, space=self.space):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = account_for_space(self.space)
        context.update({
            "recognition_subject": self.space,
            "recognition_subject_kind": "space",
            "space": self.space,
            "account": account,
            "credits_display": compact_credits(account.points_balance if account else 0),
            "ledger_entries": account.ledger_entries.all()[:30] if account else (),
            "achievements": account.achievement_grants.select_related("achievement").all() if account else (),
            "rewards": active_rewards(),
            "can_spend": can(self.request.user, PermissionCode.SPACE_RECOGNITION_SPEND, space=self.space),
        })
        return context


class RedeemRewardView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, reward_id):
        reward = get_object_or_404(RewardDefinition, pk=reward_id)
        space_id = request.POST.get("owner_space_id")
        if space_id:
            space = get_object_or_404(Organization, pk=space_id)
            if not can(request.user, PermissionCode.SPACE_RECOGNITION_SPEND, space=space):
                raise PermissionDenied
            account = get_or_create_account(space=space)
            beneficiary_profile = None
            beneficiary_space = space
            redirect_to = "recognition:space-dashboard"
            redirect_kwargs = {"space_id": space.pk}
        else:
            account = get_or_create_account(profile=request.user)
            beneficiary_profile = request.user
            beneficiary_space = None
            redirect_to = "recognition:dashboard"
            redirect_kwargs = {}
        other_profile_id = request.POST.get("beneficiary_profile_id")
        other_space_id = request.POST.get("beneficiary_space_id")
        if other_profile_id or other_space_id:
            if not reward.beneficiary_allowed:
                raise PermissionDenied
            if other_profile_id and other_space_id:
                raise Http404
            if other_profile_id:
                from django.contrib.auth import get_user_model
                beneficiary_profile = get_object_or_404(get_user_model(), pk=other_profile_id)
                beneficiary_space = None
            else:
                beneficiary_space = get_object_or_404(Organization, pk=other_space_id)
                beneficiary_profile = None
        try:
            redeem_reward(
                owner_account=account,
                reward=reward,
                idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
                actor_profile=request.user,
                beneficiary_profile=beneficiary_profile,
                beneficiary_space=beneficiary_space,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Utilisation enregistrée. Makolo prépare la suite.")
        return redirect(redirect_to, **redirect_kwargs)

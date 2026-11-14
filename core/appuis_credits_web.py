"""Two-level Appuis credit spending page (Recognition remains the owner)."""
import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.console_context import authorized_spaces
from recognition.economy import redeem_reward
from recognition.models import RewardKind
from recognition.presentation import reward_spend_presentation
from recognition.selectors import account_for_profile, account_for_space, active_rewards
from recognition.valuation import credit_money_equivalent


class AppuisCreditsWebView(LoginRequiredMixin, TemplateView):
    template_name = "core/appuis_credits.html"
    login_url = "core:login"

    def _subject(self):
        slug = self.kwargs.get("slug")
        if slug is None:
            return None
        space = get_object_or_404(authorized_spaces(self.request.user), slug=slug)
        if not can(
            self.request.user, PermissionCode.SPACE_RECOGNITION_VIEW, space=space
        ):
            raise PermissionDenied("Consultation des crédits de cet Espace non autorisée.")
        return space

    def _owner(self):
        space = self._subject()
        account = account_for_space(space) if space else account_for_profile(self.request.user)
        can_spend = bool(
            account is not None and (
                space is None or can(
                    self.request.user,
                    PermissionCode.SPACE_RECOGNITION_SPEND, space=space,
                )
            )
        )
        return space, account, can_spend

    def _links(self, space):
        if space:
            return (
                reverse("organizations:space-us-appuis", kwargs={"slug": space.slug}),
                reverse("organizations:space-us-appuis-use", kwargs={"slug": space.slug}),
            )
        return reverse("core:participant-appuis"), reverse("core:participant-appuis-use")

    def _rewards(self, account):
        if account is None:
            return []
        return [
            reward for reward in active_rewards(owner_account=account)
            if reward.kind != RewardKind.PAYOUT
            and getattr(reward, "recognition_self_eligible", False)
        ][:50]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        space, account, can_spend = self._owner()
        back_url, self_url = self._links(space)
        rewards = self._rewards(account)
        represented = [
            {"reward": reward, "presentation": reward_spend_presentation(reward),
             "token": str(uuid.uuid4())}
            for reward in rewards
        ]
        context.update(
            is_space=space is not None,
            space=space,
            back_url=back_url,
            self_url=self_url,
            credits=account.points_balance if account else 0,
            monetary_equivalent=credit_money_equivalent(account),
            features=[item for item in represented if item["presentation"]["category"] == "feature"],
            subscriptions=[item for item in represented if item["presentation"]["category"] == "subscription"],
            benefits=[item for item in represented if item["presentation"]["category"] not in {"feature", "subscription"}],
            has_rewards=bool(represented),
            can_spend=can_spend,
            error_message=kwargs.get("error_message", ""),
        )
        return context

    def post(self, request, *args, **kwargs):
        space, account, can_spend = self._owner()
        if not can_spend:
            raise PermissionDenied("Utilisation des crédits non autorisée.")
        try:
            reward_id = uuid.UUID(str(request.POST.get("reward_id") or ""))
            intent_key = uuid.UUID(str(request.POST.get("intent_key") or ""))
        except ValueError:
            return self.render_to_response(
                self.get_context_data(error_message="Choisissez une récompense disponible."),
                status=400,
            )
        reward = next((item for item in self._rewards(account) if item.pk == reward_id), None)
        if reward is None:
            return self.render_to_response(
                self.get_context_data(error_message="Cette récompense n'est plus disponible."),
                status=409,
            )
        try:
            redemption = redeem_reward(
                owner_account=account,
                reward=reward,
                idempotency_key="appuis-web:" + str(intent_key),
                actor_profile=request.user,
                beneficiary_space=space if space else None,
                beneficiary_profile=None if space else request.user,
            )
        except (ValidationError, PermissionDenied) as exc:
            message = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            return self.render_to_response(
                self.get_context_data(error_message=message), status=409,
            )
        if redemption.status == "fulfilled":
            messages.success(request, "Votre avantage est activé.")
        else:
            messages.success(request, "Votre demande est enregistrée.")
        _, self_url = self._links(space)
        return redirect(self_url)

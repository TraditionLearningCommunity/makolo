from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from .contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from .product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from .product_preview import build_subscription_change_preview
from .product_read import build_subscription_product_view
from .runtime_models import Subscription
from .security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)


def _profile_subscription(actor):
    subscription = Subscription.objects.select_related("profile").filter(profile=actor).first()
    if subscription is None:
        raise Http404("Aucun abonnement personnel n’est disponible.")
    return subscription


class ProfileSubscriptionView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = _profile_subscription(self.request.user)
        context["product"] = build_subscription_product_view(subscription, can_manage=True)
        return context


class ProfileSubscriptionPreviewView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = _profile_subscription(self.request.user)
        target = get_self_service_target(subscription, self.kwargs["plan_version_id"])
        kind = transition_kind_for_target(target)
        context.update(
            {
                "product_preview": build_subscription_change_preview(
                    subscription=subscription,
                    kind=kind,
                    target_plan_version=target,
                ),
                "idempotency_key": secrets.token_urlsafe(24),
                "confirm_url_name": "subscriptions:change",
                "back_url_name": "subscriptions:home",
                "can_confirm": True,
            }
        )
        return context


class ProfileSubscriptionChangeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, plan_version_id):
        subscription = _profile_subscription(request.user)
        target = get_self_service_target(subscription, plan_version_id)
        kind = transition_kind_for_target(target)
        try:
            transition = request_subscription_transition_for_actor(
                actor=request.user,
                subscription_id=subscription.pk,
                kind=kind,
                target_plan_version_id=target.pk,
                request_origin="self_service",
                idempotency_key=(request.POST.get("idempotency_key") or "").strip(),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("subscriptions:home")
        messages.success(request, "Votre demande de changement a été enregistrée.")
        if transition.status == SubscriptionTransitionStatus.COMPLETED:
            messages.success(request, "Votre nouvelle formule est déjà active.")
        return redirect("subscriptions:home")


class ProfileAddonRemovePreviewView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = _profile_subscription(self.request.user)
        item = get_active_addon(subscription, self.kwargs["item_id"])
        context.update(
            {
                "product_preview": build_subscription_change_preview(
                    subscription=subscription,
                    kind=SubscriptionTransitionKind.ADDON_REMOVE,
                    source_item=item,
                ),
                "idempotency_key": secrets.token_urlsafe(24),
                "confirm_url_name": "subscriptions:addon-remove",
                "confirm_item_id": str(item.pk),
                "back_url_name": "subscriptions:home",
                "can_confirm": True,
            }
        )
        return context


class ProfileAddonRemoveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, item_id):
        subscription = _profile_subscription(request.user)
        item = get_active_addon(subscription, item_id)
        try:
            request_subscription_transition_for_actor(
                actor=request.user,
                subscription_id=subscription.pk,
                kind=SubscriptionTransitionKind.ADDON_REMOVE,
                source_item_id=item.pk,
                request_origin="self_service",
                idempotency_key=(request.POST.get("idempotency_key") or "").strip(),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("subscriptions:home")
        messages.success(request, "La demande de retrait de l’option a été enregistrée.")
        return redirect("subscriptions:home")


class ProfileTransitionCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, transition_id):
        try:
            cancel_subscription_transition_for_actor(
                actor=request.user,
                transition_id=transition_id,
                reason="Annulée depuis l’interface Abonnement.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "La demande a été annulée.")
        return redirect("subscriptions:home")


class ProfileTransitionCompleteView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, transition_id):
        try:
            complete_subscription_transition_for_actor(actor=request.user, transition_id=transition_id)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Le changement de formule est terminé.")
        return redirect("subscriptions:home")

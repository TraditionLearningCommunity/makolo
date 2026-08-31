from __future__ import annotations

import secrets

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from subscriptions.authorization import subscriptions_visible_to_actor
from subscriptions.contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from subscriptions.product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from subscriptions.product_preview import build_subscription_change_preview
from subscriptions.product_read import build_subscription_product_view
from subscriptions.security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)

from .console_views import SpaceConsoleMixin


class SpaceSubscriptionMixin(SpaceConsoleMixin):
    module_key = "subscription"
    page_title = "Abonnement"

    def get_subscription(self):
        subscription = (
            subscriptions_visible_to_actor(self.request.user)
            .select_related("space")
            .filter(space=self.space)
            .first()
        )
        if subscription is None:
            raise Http404("Aucun abonnement n’est disponible pour cet Espace.")
        return subscription

    def require_manage(self):
        if not self.space_console.can_manage_subscription:
            raise PermissionDenied("La permission de gestion de l’abonnement de cet Espace est requise.")


class SpaceConsoleSubscriptionView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
        context["product"] = build_subscription_product_view(
            subscription,
            can_manage=self.space_console.can_manage_subscription,
        )
        return context


class SpaceSubscriptionPreviewView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
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
                "confirm_url_name": "organizations:console-subscription-change",
                "back_url_name": "organizations:console-subscription",
                "space_slug": self.space.slug,
                "can_confirm": self.space_console.can_manage_subscription,
            }
        )
        return context


class SpaceSubscriptionChangeView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        subscription = self.get_subscription()
        target = get_self_service_target(subscription, self.kwargs["plan_version_id"])
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
        else:
            messages.success(request, "La demande de changement de l’Espace a été enregistrée.")
            if transition.status == SubscriptionTransitionStatus.COMPLETED:
                messages.success(request, "La nouvelle formule de l’Espace est active.")
        return redirect("organizations:console-subscription", slug=self.space.slug)


class SpaceAddonRemovePreviewView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
        item = get_active_addon(subscription, self.kwargs["item_id"])
        context.update(
            {
                "product_preview": build_subscription_change_preview(
                    subscription=subscription,
                    kind=SubscriptionTransitionKind.ADDON_REMOVE,
                    source_item=item,
                ),
                "idempotency_key": secrets.token_urlsafe(24),
                "confirm_url_name": "organizations:console-subscription-addon-remove",
                "confirm_item_id": str(item.pk),
                "back_url_name": "organizations:console-subscription",
                "space_slug": self.space.slug,
                "can_confirm": self.space_console.can_manage_subscription,
            }
        )
        return context


class SpaceAddonRemoveView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        subscription = self.get_subscription()
        item = get_active_addon(subscription, self.kwargs["item_id"])
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
        else:
            messages.success(request, "La demande de retrait de l’option a été enregistrée.")
        return redirect("organizations:console-subscription", slug=self.space.slug)


class SpaceTransitionCancelView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        try:
            cancel_subscription_transition_for_actor(
                actor=request.user,
                transition_id=self.kwargs["transition_id"],
                reason="Annulée depuis la Console Espace.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "La demande a été annulée.")
        return redirect("organizations:console-subscription", slug=self.space.slug)


class SpaceTransitionCompleteView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        try:
            complete_subscription_transition_for_actor(
                actor=request.user,
                transition_id=self.kwargs["transition_id"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Le changement de formule de l’Espace est terminé.")
        return redirect("organizations:console-subscription", slug=self.space.slug)

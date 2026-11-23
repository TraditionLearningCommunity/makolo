from __future__ import annotations

import secrets

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from subscriptions.authorization import subscriptions_visible_to_actor
from subscriptions.billing_models import PlanVersionBillingTerms
from subscriptions.billing_presentation import (
    next_payment_url_for_actor, terms_as_dict,
    transition_payment_action_for_actor, with_billing_terms,
)
from subscriptions.space_billing_view import space_billing_for_actor
from subscriptions.personal_history import subscription_transition_history
from subscriptions.contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from subscriptions.product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from subscriptions.product_preview import build_subscription_change_preview
from subscriptions.product_read import build_subscription_product_view
from subscriptions.security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)
from subscriptions.transition_models import SubscriptionTransition
from subscriptions.coverage_models import SubscriptionCoverage, SubscriptionCoverageAllocation
from subscriptions.coverage_services import (
    accept_coverage_allocation, decide_coverage_allocation,
    select_coverage_base, use_personal_base,
)
from subscriptions.ux_continuation import safe_action_return, subscription_return_home

from .console_views import SpaceConsoleMixin


class SpaceSubscriptionMixin(SpaceConsoleMixin):
    module_key = "subscription"
    page_title = "Abonnement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subscription_return_url"] = safe_action_return(
            self.request, space=self.space,
        )
        return context

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

    def get_transition(self, subscription, transition_id):
        return get_object_or_404(
            SubscriptionTransition,
            pk=transition_id,
            subscription=subscription,
        )


class SpaceConsoleSubscriptionView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
        context["product"] = with_billing_terms(build_subscription_product_view(
            subscription,
            can_manage=self.space_console.can_manage_subscription,
        ))
        context["space_billing"] = space_billing_for_actor(self.request.user, subscription)
        context["space_history"] = subscription_transition_history(subscription)
        context["coverage_received"] = (
            SubscriptionCoverageAllocation.objects.filter(space=self.space)
            .select_related("coverage__plan_version__plan")
            .order_by("-created_at")[:30]
        )
        if self.space_console.can_manage_subscription:
            context["coverage_financed"] = (
                SubscriptionCoverage.objects.filter(payer_space=self.space)
                .select_related("plan_version").order_by("-created_at")[:30]
            )
        else:
            context["coverage_financed"] = ()

        context["subscription_return_url"] = safe_action_return(self.request, space=self.space)
        product = context["product"]
        if product.transition and product.transition["open"] and product.can_manage:
            transition = SubscriptionTransition.objects.get(
                pk=product.transition["id"], subscription=subscription,
            )
            context["transition_financial"] = transition_payment_action_for_actor(
                transition, actor=self.request.user,
            )
            context["transition_payment_url"] = next_payment_url_for_actor(
                transition, self.request.user,
            )
        return context


class SpaceSubscriptionBillingView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription_billing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            offset = int(self.request.GET.get("offset", "0"))
        except (ValueError, TypeError):
            offset = 0
        offset = offset if 0 <= offset <= 500 else 0
        context["space_billing"] = space_billing_for_actor(
            self.request.user, self.get_subscription(), offset=offset,
        )
        return context


class SpaceSubscriptionHistoryView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            offset = int(self.request.GET.get("offset", "0"))
        except (ValueError, TypeError):
            offset = 0
        offset = offset if 0 <= offset <= 100000 else 0
        context["space_history"] = subscription_transition_history(
            self.get_subscription(), offset=offset,
        )
        return context


class SpaceSubscriptionPreviewView(SpaceSubscriptionMixin, TemplateView):
    template_name = "organizations/console/subscription_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
        target = get_self_service_target(subscription, self.kwargs["plan_version_id"])
        kind = transition_kind_for_target(target)
        preview = build_subscription_change_preview(
            subscription=subscription, kind=kind, target_plan_version=target,
        )
        preview["billing_terms"] = terms_as_dict(
            PlanVersionBillingTerms.objects.filter(plan_version=target).first()
        )
        context.update(
            {
                "product_preview": preview,
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
            if transition.status == SubscriptionTransitionStatus.COMPLETED:
                messages.success(request, "La nouvelle formule de l’Espace est active.")
            else:
                payment_url = next_payment_url_for_actor(transition, request.user)
                if payment_url:
                    messages.info(request, "Le changement est enregistré. Procédez au paiement pour l’activer.")
                    return redirect(payment_url)
                messages.info(request, "Changement à finaliser. Le règlement doit être effectué par un acteur autorisé ou des conditions restent à remplir.")
        return redirect(subscription_return_home(request, space=self.space))


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
            transition = request_subscription_transition_for_actor(
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
            messages.success(request, "Option retirée." if transition.status == SubscriptionTransitionStatus.COMPLETED else "Retrait de l’option à finaliser.")
        return redirect(subscription_return_home(request, space=self.space))


class SpaceTransitionCancelView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        subscription = self.get_subscription()
        transition = self.get_transition(subscription, self.kwargs["transition_id"])
        try:
            cancel_subscription_transition_for_actor(
                actor=request.user,
                transition_id=transition.pk,
                reason="Annulée depuis la Console Espace.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "La demande a été annulée.")
        return redirect(subscription_return_home(request, space=self.space))


class SpaceTransitionCompleteView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        subscription = self.get_subscription()
        transition = self.get_transition(subscription, self.kwargs["transition_id"])
        try:
            complete_subscription_transition_for_actor(
                actor=request.user,
                transition_id=transition.pk,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Le changement de formule de l’Espace est terminé.")
        return redirect(subscription_return_home(request, space=self.space))


class SpaceCoverageDecisionView(SpaceSubscriptionMixin, View):
    def post(self, request, *args, **kwargs):
        self.require_manage()
        allocation = get_object_or_404(
            SubscriptionCoverageAllocation.objects.select_related("coverage__plan_version__plan"),
            pk=self.kwargs["allocation_id"], space=self.space,
        )
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "accept":
                accept_coverage_allocation(
                    actor=request.user, allocation=allocation,
                    select_base=allocation.coverage.plan_version.plan.plan_type == "base",
                )
            elif action == "decline":
                decide_coverage_allocation(
                    actor=request.user, allocation=allocation,
                    reason="Refus par l'Espace bénéficiaire.",
                )
            elif action == "select_base":
                select_coverage_base(actor=request.user, allocation=allocation)
            elif action == "use_personal_base":
                use_personal_base(actor=request.user, space=self.space)
            else:
                raise ValidationError("Action de couverture inconnue.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Le choix de couverture de l'Espace a été enregistré.")
        return redirect("organizations:console-subscription", slug=self.space.slug)

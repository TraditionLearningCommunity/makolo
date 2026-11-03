from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .billing_models import PlanVersionBillingTerms
from .billing_presentation import (
    next_payment_url_for_actor, personal_billing_obligations, terms_as_dict,
    transition_payment_action_for_actor, with_billing_terms,
)
from .contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from .product_actions import get_active_addon, get_self_service_target, transition_kind_for_target
from .product_preview import build_subscription_change_preview
from .product_read import build_subscription_product_view
from .personal_history import personal_transition_history
from .runtime_models import Subscription
from .coverage_models import SubscriptionCoverageAllocation, SubscriptionCoverage
from .coverage_services import (
    accept_coverage_allocation, decide_coverage_allocation,
    select_coverage_base, use_personal_base,
)
from .security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    request_subscription_transition_for_actor,
)
from .transition_models import SubscriptionTransition
from .ux_continuation import safe_action_return, subscription_return_home


def _profile_subscription(actor):
    subscription = Subscription.objects.select_related("profile").filter(profile=actor).first()
    if subscription is None:
        raise Http404("Aucun abonnement personnel n’est disponible.")
    return subscription


def _profile_transition(subscription, transition_id):
    return get_object_or_404(
        SubscriptionTransition,
        pk=transition_id,
        subscription=subscription,
    )


class ProfileSubscriptionView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = _profile_subscription(self.request.user)
        context["product"] = with_billing_terms(build_subscription_product_view(subscription, can_manage=True))
        context["personal_billing"] = personal_billing_obligations(subscription)
        context["personal_history"] = personal_transition_history(subscription)
        context["coverage_received"] = (
            SubscriptionCoverageAllocation.objects.filter(profile=self.request.user)
            .select_related("coverage__plan_version__plan")
            .order_by("-created_at")[:30]
        )
        context["coverage_financed"] = (
            SubscriptionCoverage.objects.filter(payer_profile=self.request.user)
            .select_related("plan_version")
            .order_by("-created_at")[:30]
        )
        context["subscription_return_url"] = safe_action_return(self.request)
        product = context["product"]
        if product.transition and product.transition["open"]:
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


class ProfileSubscriptionHistoryView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            offset = int(self.request.GET.get("offset", "0"))
        except (TypeError, ValueError):
            offset = 0
        offset = offset if 0 <= offset <= 100000 else 0
        context["personal_history"] = personal_transition_history(
            _profile_subscription(self.request.user), offset=offset,
        )
        return context


class ProfileSubscriptionBillingView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile_billing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            offset = int(self.request.GET.get("offset", "0"))
        except (TypeError, ValueError):
            offset = 0
        offset = offset if 0 <= offset <= 500 else 0
        context["personal_billing"] = personal_billing_obligations(
            _profile_subscription(self.request.user), offset=offset,
        )
        context["billing_offset"] = offset
        return context


class ProfileSubscriptionPreviewView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "subscriptions/profile_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = _profile_subscription(self.request.user)
        target = get_self_service_target(subscription, self.kwargs["plan_version_id"])
        kind = transition_kind_for_target(target)
        terms = PlanVersionBillingTerms.objects.filter(plan_version=target).first()
        preview = build_subscription_change_preview(
            subscription=subscription, kind=kind, target_plan_version=target,
        )
        preview["billing_terms"] = terms_as_dict(terms)
        context.update(
            {
                "product_preview": preview,
                "subscription_return_url": safe_action_return(self.request),
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
            return redirect(subscription_return_home(request))
        if transition.status == SubscriptionTransitionStatus.COMPLETED:
            messages.success(request, "Votre nouvelle formule est active.")
        else:
            payment_url = next_payment_url_for_actor(transition, request.user)
            if payment_url:
                messages.info(request, "Votre choix est enregistré. Vous pouvez payer maintenant ou reprendre plus tard.")
                return redirect(payment_url)
            messages.info(request, "Le changement est enregistré. Consultez les conditions restant à finaliser.")
        return redirect(subscription_return_home(request))


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
                "subscription_return_url": safe_action_return(self.request),
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
            return redirect(subscription_return_home(request))
        messages.success(request, "Option retirée." if transition.status == SubscriptionTransitionStatus.COMPLETED else "Retrait de l’option à finaliser.")
        return redirect(subscription_return_home(request))


class ProfileTransitionCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, transition_id):
        subscription = _profile_subscription(request.user)
        transition = _profile_transition(subscription, transition_id)
        try:
            cancel_subscription_transition_for_actor(
                actor=request.user,
                transition_id=transition.pk,
                reason="Annulée depuis l’interface Abonnement.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "La demande a été annulée.")
        return redirect(subscription_return_home(request))


class ProfileTransitionCompleteView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, transition_id):
        subscription = _profile_subscription(request.user)
        transition = _profile_transition(subscription, transition_id)
        try:
            complete_subscription_transition_for_actor(actor=request.user, transition_id=transition.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Le changement de formule est terminé.")
        return redirect(subscription_return_home(request))


class ProfileCoverageDecisionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, allocation_id):
        allocation = get_object_or_404(
            SubscriptionCoverageAllocation.objects.select_related("coverage__plan_version__plan"),
            pk=allocation_id, profile=request.user,
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
                    reason="Refus par le bénéficiaire.",
                )
            elif action == "select_base":
                select_coverage_base(actor=request.user, allocation=allocation)
            elif action == "use_personal_base":
                use_personal_base(actor=request.user, profile=request.user)
            else:
                raise ValidationError("Action de couverture inconnue.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Votre choix de couverture a été enregistré.")
        return redirect("subscriptions:home")

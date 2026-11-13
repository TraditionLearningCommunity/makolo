"""Shared Profile/Space web composition of established owner appuis.

Recognition, Loyalty and Partners remain authoritative. No global balance,
new entitlement, proxy mutation or duplicate personal/Space screen.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from loyalty.models import LoyaltyProgram
from loyalty.permissions import user_can_view_loyalty_workspace
from loyalty.selectors import (
    get_accounts_visible_to,
    get_subscriptions_visible_to,
    personal_rewards_available_to,
)
from organizations.console_context import authorized_spaces
from partners.models import PartnerStatus
from partners.selectors import (
    get_campaigns_visible_to,
    get_commissions_visible_to,
    get_partners_visible_to,
    get_payouts_visible_to,
    get_referral_codes_visible_to,
)
from recognition.models import RecognitionRedemption
from recognition.selectors import (
    account_for_profile,
    account_for_space,
    active_rewards,
    redemptions_requiring_beneficiary_response,
)


class AppuisWebView(LoginRequiredMixin, TemplateView):
    template_name = "core/appuis.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        viewer = self.request.user
        slug = kwargs.get("slug")
        space = (
            get_object_or_404(authorized_spaces(viewer), slug=slug)
            if slug is not None else None
        )
        context["space"] = space
        context["is_space"] = space is not None
        context["back_url"] = (
            reverse("organizations:space-us", kwargs={"slug": space.slug})
            if space is not None else reverse("core:participant-me")
        )

        if space is not None:
            recognition_visible = can(
                viewer, PermissionCode.SPACE_RECOGNITION_VIEW, space=space
            )
            recognition_account = (
                account_for_space(space) if recognition_visible else None
            )
            context["recognition_url"] = (
                reverse("recognition:space-dashboard",
                        kwargs={"space_id": space.pk})
                if recognition_visible else None
            )
            loyalty_visible = user_can_view_loyalty_workspace(viewer, space)
            context["loyalty_program"] = (
                LoyaltyProgram.objects.filter(
                    organization=space, is_active=True
                ).prefetch_related("tiers", "membership_plans", "rewards").first()
                if loyalty_visible else None
            )
            context["loyalty_url"] = (
                reverse("loyalty:workspace", kwargs={"slug": space.slug})
                if loyalty_visible else None
            )
            context["loyalty_accounts"] = ()
            context["loyalty_memberships"] = ()
            context["loyalty_rewards"] = ()
            context["partners"] = (
                get_partners_visible_to(viewer)
                .filter(organization=space, status=PartnerStatus.ACTIVE)
                .select_related("organization")
                .order_by("name", "pk")[:50]
            )
            context["partner_is_personal"] = False
        else:
            recognition_account = account_for_profile(viewer)
            context["recognition_url"] = reverse("recognition:dashboard")
            context["loyalty_program"] = None
            context["loyalty_url"] = reverse("loyalty:dashboard")
            context["loyalty_accounts"] = (
                get_accounts_visible_to(viewer).filter(user=viewer)
                .select_related("program__organization", "current_tier")
                .order_by("program__organization__name", "pk")[:50]
            )
            context["loyalty_memberships"] = (
                get_subscriptions_visible_to(viewer).filter(user=viewer)
                .select_related("program__organization", "plan")
                .order_by("-requested_at", "pk")[:50]
            )
            context["loyalty_rewards"] = list(
                personal_rewards_available_to(viewer)[:50]
            )
            context["partners"] = (
                get_partners_visible_to(viewer)
                .filter(user=viewer, status=PartnerStatus.ACTIVE)
                .select_related("organization")
                .order_by("organization__name", "pk")[:50]
            )
            context["partner_is_personal"] = True

        # Every Partner projection is scoped back to the established,
        # actor-visible relationships before its owner detail is displayed.
        partner_ids = [row.pk for row in context["partners"]]
        context["partner_codes"] = (
            get_referral_codes_visible_to(viewer)
            .filter(partner_id__in=partner_ids)
            .select_related("partner", "campaign")
            .order_by("pk")[:50]
        )
        context["partner_campaigns"] = (
            get_campaigns_visible_to(viewer)
            .filter(referral_codes__partner_id__in=partner_ids)
            .distinct().order_by("name", "pk")[:50]
        )
        context["partner_commissions"] = (
            get_commissions_visible_to(viewer)
            .filter(partner_id__in=partner_ids)
            .order_by("-earned_at", "pk")[:50]
        )
        context["partner_payouts"] = (
            get_payouts_visible_to(viewer)
            .filter(partner_id__in=partner_ids)
            .order_by("-created_at", "pk")[:50]
        )
        context["recognition_account"] = recognition_account
        context["recognition_achievements"] = (
            recognition_account.achievement_grants.select_related(
                "achievement"
            ).order_by("-granted_at", "pk")[:20]
            if recognition_account is not None else ()
        )
        context["recognition_rewards"] = (
            active_rewards(owner_account=recognition_account)[:20]
            if recognition_account is not None else ()
        )
        context["recognition_recent"] = (
            recognition_account.ledger_entries.order_by("-created_at", "pk")[:20]
            if recognition_account is not None else ()
        )
        if space is None:
            recognition_incoming = redemptions_requiring_beneficiary_response(
                viewer
            )[:20]
        elif can(
            viewer, PermissionCode.SPACE_RECOGNITION_SPEND, space=space
        ):
            recognition_incoming = (
                RecognitionRedemption.objects.filter(
                    beneficiary_space=space,
                    status="requested",
                    fulfillment_snapshot__consent_state="pending",
                ).order_by("created_at", "pk")[:20]
            )
        else:
            recognition_incoming = ()
        context["recognition_incoming"] = recognition_incoming
        context["recognition_available"] = (
            recognition_account is not None
            or bool(context["recognition_incoming"])
        )
        context["appuis_available"] = (
            context["recognition_available"]
            or context["loyalty_program"] is not None
            or bool(context["loyalty_accounts"])
            or bool(context["loyalty_memberships"])
            or bool(context["loyalty_rewards"])
            or bool(context["partners"])
        )
        return context

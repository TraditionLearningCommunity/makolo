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

        # Web and Flutter share the same display rule: a real owner element
        # remains visible with zero points, but zero is never a headline.
        account_rows = list(context["loyalty_accounts"])
        membership_rows = list(context["loyalty_memberships"])
        reward_rows = list(context["loyalty_rewards"])
        partner_rows = list(context["partners"])
        achievement_rows = list(context["recognition_achievements"])
        recognition_reward_rows = list(context["recognition_rewards"])
        incoming_rows = list(context["recognition_incoming"])

        if space is None or recognition_visible:
            recognition_benefits = list(
                RecognitionRedemption.objects.filter(
                    **(
                        {"beneficiary_space": space}
                        if space is not None else {"beneficiary_profile": viewer}
                    )
                ).select_related("reward").order_by("-created_at", "-pk")[:20]
            )
        else:
            recognition_benefits = []
        context["recognition_benefits"] = recognition_benefits

        loyalty_cards = {}
        for account in account_rows:
            program = account.program
            loyalty_cards[str(program.pk)] = {
                "name": program.name,
                "organization": program.organization.name,
                "url": reverse("loyalty:portal", kwargs={
                    "slug": program.organization.slug}),
                "balance": account.points_balance if account.points_balance > 0 else None,
                "unit": program.points_name,
                "tier": account.current_tier.name if account.current_tier else None,
            }
        for membership in membership_rows:
            program = membership.program
            loyalty_cards.setdefault(str(program.pk), {
                "name": program.name,
                "organization": program.organization.name,
                "url": reverse("loyalty:portal", kwargs={
                    "slug": program.organization.slug}),
                "balance": None, "unit": program.points_name, "tier": None,
            })
        for reward in reward_rows:
            program = reward.program
            loyalty_cards.setdefault(str(program.pk), {
                "name": program.name,
                "organization": program.organization.name,
                "url": reverse("loyalty:portal", kwargs={
                    "slug": program.organization.slug}),
                "balance": None, "unit": program.points_name, "tier": None,
            })
        if context["loyalty_program"] is not None:
            program = context["loyalty_program"]
            loyalty_cards[str(program.pk)] = {
                "name": program.name,
                "organization": program.organization.name,
                "url": context["loyalty_url"],
                "balance": None, "unit": program.points_name, "tier": None,
            }
        context["loyalty_cards"] = list(loyalty_cards.values())

        recognition_cards = []
        for row in incoming_rows:
            recognition_cards.append({
                "title": row.reward.name, "subtitle": "Réponse attendue",
                "symbol": "bell-ring",
            })
        for row in recognition_reward_rows:
            recognition_cards.append({
                "title": row.name, "subtitle": "Récompense disponible",
                "symbol": "gift",
            })
        for row in achievement_rows:
            recognition_cards.append({
                "title": row.achievement.name,
                "subtitle": row.achievement.badge_label or "Contribution reconnue",
                "symbol": "award",
            })
        incoming_ids = {row.pk for row in incoming_rows}
        for row in recognition_benefits:
            if row.pk in incoming_ids:
                continue
            recognition_cards.append({
                "title": row.reward.name, "subtitle": row.get_status_display(),
                "symbol": "badge-check",
            })
        context["recognition_cards"] = recognition_cards

        recognition_credits = (
            recognition_account.points_balance
            if recognition_account is not None and recognition_account.points_balance > 0
            else None
        )
        context["recognition_credits"] = recognition_credits
        context["has_recognition_appuis"] = bool(
            recognition_credits is not None or recognition_cards or
            context["recognition_recent"]
        )
        context["has_loyalty_appuis"] = bool(loyalty_cards)
        context["has_partner_appuis"] = bool(partner_rows)
        context["partner_cards"] = partner_rows

        metrics = []
        if loyalty_cards:
            metrics.append({
                "icon": "gift", "value": len(loyalty_cards),
                "label": "programme" if len(loyalty_cards) == 1 else "programmes",
            })
        # Never add Recognition rewards to Loyalty rewards or their balances.
        recognition_count = len(achievement_rows) or len(recognition_reward_rows)
        if recognition_count > 0:
            metrics.append({
                "icon": "award", "value": recognition_count,
                "label": (
                    "reconnaissance" if len(achievement_rows) == 1
                    else "reconnaissances"
                ) if achievement_rows else (
                    "récompense" if recognition_count == 1 else "récompenses"
                ),
            })
        elif recognition_credits is not None:
            metrics.append({
                "icon": "star", "value": recognition_credits,
                "label": "crédit Recognition" if recognition_credits == 1
                         else "crédits Recognition",
            })
        if partner_rows:
            metrics.append({
                "icon": "handshake", "value": len(partner_rows),
                "label": "partenariat" if len(partner_rows) == 1 else "partenariats",
            })
        context["appuis_metrics"] = metrics
        context["appuis_family_count"] = sum((
            bool(context["has_recognition_appuis"]),
            bool(context["has_loyalty_appuis"]),
            bool(context["has_partner_appuis"]),
        ))
        context["appuis_available"] = bool(
            context["has_recognition_appuis"] or
            context["has_loyalty_appuis"] or
            context["has_partner_appuis"]
        )
        return context

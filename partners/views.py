from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .forms import AffiliateCampaignForm, PartnerForm, ReferralCodeForm
from .models import AffiliateCampaign, Partner, PartnerPayout, PayoutStatus, ReferralCode
from .permissions import user_can_manage_partner_payouts, user_can_manage_partners, user_can_view_partner, user_can_view_partner_finance
from .selectors import get_campaigns_visible_to, get_partners_visible_to, get_payouts_visible_to, get_referral_codes_visible_to
from .services import (
    build_partner_metrics,
    cancel_payout,
    capture_referral_request,
    create_campaign,
    create_partner,
    create_payout,
    create_referral_code,
    mark_payout_paid,
    partner_balance,
)


def _partner_workspace_spaces(user):
    marketing_ids = space_ids_with_permission(user, PermissionCode.PARTNERS_MANAGE)
    finance_ids = space_ids_with_permission(user, PermissionCode.PARTNERS_FINANCE)
    queryset = Organization.objects.all().order_by("name")
    if marketing_ids is None or finance_ids is None:
        return queryset
    return queryset.filter(pk__in=set(marketing_ids) | set(finance_ids))


class PartnerDashboardView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = "partners/dashboard.html"
    context_object_name = "partners"
    login_url = "core:login"
    paginate_by = 30

    def get_queryset(self):
        return get_partners_visible_to(self.request.user).annotate(
            codes_count=Count("referral_codes", distinct=True),
            conversions_count=Count("attributions", distinct=True),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["campaigns"] = get_campaigns_visible_to(self.request.user)[:20]
        context["my_partner_profiles"] = Partner.objects.filter(user=self.request.user).select_related("organization")
        context["manageable_organizations"] = _partner_workspace_spaces(self.request.user)
        return context


class OrganizationPartnerView(LoginRequiredMixin, View):
    login_url = "core:login"

    def _organization(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not (user_can_manage_partners(request.user, organization) or user_can_view_partner_finance(request.user, organization)):
            raise PermissionDenied("Vous n’avez pas accès aux partenaires de cet Espace.")
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        partners = get_partners_visible_to(request.user).filter(organization=organization)
        campaigns = get_campaigns_visible_to(request.user).filter(organization=organization)
        payouts = get_payouts_visible_to(request.user).filter(organization=organization)[:20]
        return render(
            request,
            "partners/organization.html",
            {
                "organization": organization,
                "partners": partners,
                "campaigns": campaigns,
                "payouts": payouts,
                "can_manage": user_can_manage_partners(request.user, organization),
                "can_finance": user_can_view_partner_finance(request.user, organization),
            },
        )


class PartnerCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def _organization(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_partners(request.user, organization):
            raise PermissionDenied
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        return render(request, "partners/form.html", {"form": PartnerForm(), "title": "Nouveau partenaire", "organization": organization})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        form = PartnerForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            partner = create_partner(
                organization=organization,
                actor=request.user,
                name=data["name"],
                email=data["email"],
                phone=data["phone"],
                kind=data["kind"],
                user=getattr(form, "linked_user", None),
                notes=data["notes"],
            )
            if data.get("public_label"):
                partner.public_label = data["public_label"]
                partner.save(update_fields=["public_label", "updated_at"])
            messages.success(request, "Partenaire créé. Vous pouvez maintenant lui attribuer un code de campagne.")
            return redirect("partners:partner-detail", pk=partner.pk)
        return render(request, "partners/form.html", {"form": form, "title": "Nouveau partenaire", "organization": organization}, status=400)


class CampaignCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def _organization(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not user_can_manage_partners(request.user, organization):
            raise PermissionDenied
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        return render(request, "partners/form.html", {"form": AffiliateCampaignForm(organization=organization), "title": "Nouvelle campagne d’affiliation", "organization": organization})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        form = AffiliateCampaignForm(request.POST, organization=organization)
        if form.is_valid():
            data = form.cleaned_data
            campaign = create_campaign(
                organization=organization,
                event=data["event"],
                actor=request.user,
                name=data["name"],
                commission_type=data["commission_type"],
                commission_value=data["commission_value"],
                commission_currency=data["commission_currency"],
                attribution_window_days=data["attribution_window_days"],
                starts_at=data["starts_at"],
                ends_at=data["ends_at"],
                status=data["status"],
            )
            messages.success(request, "Campagne créée.")
            return redirect("partners:campaign-detail", pk=campaign.pk)
        return render(request, "partners/form.html", {"form": form, "title": "Nouvelle campagne d’affiliation", "organization": organization}, status=400)


class CampaignDetailView(LoginRequiredMixin, DetailView):
    model = AffiliateCampaign
    template_name = "partners/campaign_detail.html"
    context_object_name = "campaign"
    login_url = "core:login"

    def get_queryset(self):
        return get_campaigns_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["codes"] = get_referral_codes_visible_to(self.request.user).filter(campaign=self.object).annotate(
            visits_count=Count("visits", distinct=True),
            conversions_count=Count("attributions", distinct=True),
        )
        context["form"] = ReferralCodeForm(campaign=self.object)
        context["can_manage"] = user_can_manage_partners(self.request.user, self.object.organization)
        context["can_finance"] = user_can_view_partner_finance(self.request.user, self.object.organization)
        return context


class ReferralCodeCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        campaign = get_object_or_404(AffiliateCampaign.objects.select_related("organization"), pk=pk)
        if not user_can_manage_partners(request.user, campaign.organization):
            raise PermissionDenied
        form = ReferralCodeForm(request.POST, campaign=campaign)
        if not form.is_valid():
            messages.error(request, "; ".join(sum(form.errors.values(), [])))
            return redirect("partners:campaign-detail", pk=campaign.pk)
        data = form.cleaned_data
        try:
            referral = create_referral_code(
                campaign=campaign,
                partner=data["partner"],
                actor=request.user,
                code=data["code"],
                commission_type_override=data["commission_type_override"],
                commission_value_override=data["commission_value_override"],
            )
            if not data["is_active"]:
                referral.is_active = False
                referral.save(update_fields=["is_active", "updated_at"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Code {referral.code} créé pour {referral.partner.display_name}.")
        return redirect("partners:campaign-detail", pk=campaign.pk)


class PartnerDetailView(LoginRequiredMixin, DetailView):
    model = Partner
    template_name = "partners/partner_detail.html"
    context_object_name = "partner"
    login_url = "core:login"

    def get_queryset(self):
        return get_partners_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        finance_visible = user_can_view_partner_finance(self.request.user, self.object.organization) or self.object.user_id == self.request.user.pk
        context["metrics"] = build_partner_metrics(self.object, finance_visible=finance_visible)
        context["codes"] = get_referral_codes_visible_to(self.request.user).filter(partner=self.object)
        context["balances"] = partner_balance(self.object) if finance_visible else []
        context["payouts"] = get_payouts_visible_to(self.request.user).filter(partner=self.object)[:20]
        context["can_finance"] = user_can_manage_partner_payouts(self.request.user, self.object.organization)
        return context


class ReferralLandingView(View):
    def get(self, request, code):
        referral = capture_referral_request(request, code)
        if not referral:
            messages.error(request, "Ce lien ambassadeur n’est plus actif.")
            return redirect("events:list")
        return redirect(f"{reverse('events:detail', kwargs={'slug': referral.campaign.event.slug})}?ref={referral.code}")


class PayoutCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        partner = get_object_or_404(Partner.objects.select_related("organization"), pk=pk)
        if not user_can_manage_partner_payouts(request.user, partner.organization):
            raise PermissionDenied
        try:
            payout = create_payout(
                partner=partner,
                actor=request.user,
                currency=request.POST.get("currency", ""),
                reference=request.POST.get("reference", ""),
                notes=request.POST.get("notes", ""),
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Paiement de commissions préparé : {payout.amount} {payout.currency}.")
        return redirect("partners:partner-detail", pk=partner.pk)


class PayoutMarkPaidView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        payout = get_object_or_404(PartnerPayout.objects.select_related("organization", "partner"), pk=pk)
        try:
            mark_payout_paid(payout=payout, actor=request.user, reference=request.POST.get("reference", ""))
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Paiement partenaire marqué comme payé.")
        return redirect("partners:partner-detail", pk=payout.partner_id)


class PayoutCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        payout = get_object_or_404(PartnerPayout.objects.select_related("organization", "partner"), pk=pk)
        try:
            cancel_payout(payout=payout, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Paiement partenaire annulé et commissions libérées.")
        return redirect("partners:partner-detail", pk=payout.partner_id)

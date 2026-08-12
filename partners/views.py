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
                partner_type=data["partner_type"],
                contact_name=data.get("contact_name", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                user=data.get("user"),
                notes=data.get("notes", ""),
            )
            messages.success(request, f"Partenaire {partner.name} créé.")
            return redirect("partners:organization", slug=organization.slug)
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
        return render(request, "partners/form.html", {"form": AffiliateCampaignForm(organization=organization), "title": "Nouvelle campagne partenaire", "organization": organization})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        form = AffiliateCampaignForm(request.POST, organization=organization)
        if form.is_valid():
            data = form.cleaned_data
            campaign = create_campaign(
                organization=organization,
                actor=request.user,
                name=data["name"],
                event=data.get("event"),
                attribution_window_days=data["attribution_window_days"],
                commission_type=data["commission_type"],
                commission_value=data["commission_value"],
                currency=data.get("currency", ""),
                starts_at=data.get("starts_at"),
                ends_at=data.get("ends_at"),
            )
            messages.success(request, f"Campagne {campaign.name} créée.")
            return redirect("partners:organization", slug=organization.slug)
        return render(request, "partners/form.html", {"form": form, "title": "Nouvelle campagne partenaire", "organization": organization}, status=400)


class ReferralCodeCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get_campaign(self, request, pk):
        campaign = get_object_or_404(AffiliateCampaign.objects.select_related("organization"), pk=pk)
        if not user_can_manage_partners(request.user, campaign.organization):
            raise PermissionDenied
        return campaign

    def get(self, request, pk):
        campaign = self.get_campaign(request, pk)
        return render(request, "partners/form.html", {"form": ReferralCodeForm(campaign=campaign), "title": "Nouveau lien partenaire", "campaign": campaign})

    def post(self, request, pk):
        campaign = self.get_campaign(request, pk)
        form = ReferralCodeForm(request.POST, campaign=campaign)
        if form.is_valid():
            data = form.cleaned_data
            referral = create_referral_code(
                campaign=campaign,
                partner=data["partner"],
                actor=request.user,
                code=data.get("code", ""),
                destination_url=data.get("destination_url", ""),
            )
            messages.success(request, f"Lien partenaire {referral.code} créé.")
            return redirect("partners:organization", slug=campaign.organization.slug)
        return render(request, "partners/form.html", {"form": form, "title": "Nouveau lien partenaire", "campaign": campaign}, status=400)


class ReferralCaptureView(View):
    def get(self, request, code):
        referral = get_object_or_404(ReferralCode.objects.select_related("campaign"), code=code.upper(), is_active=True)
        destination = capture_referral_request(referral_code=referral, request=request)
        return redirect(destination)


class PartnerDetailView(LoginRequiredMixin, DetailView):
    model = Partner
    template_name = "partners/detail.html"
    context_object_name = "partner"
    login_url = "core:login"

    def get_queryset(self):
        return get_partners_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        partner = self.object
        if not user_can_view_partner(self.request.user, partner):
            raise PermissionDenied
        campaigns = get_campaigns_visible_to(self.request.user).filter(referral_codes__partner=partner).distinct()
        metrics = [build_partner_metrics(partner=partner, campaign=campaign) for campaign in campaigns]
        context["metrics"] = metrics
        context["balance"] = partner_balance(partner=partner)
        context["can_finance"] = user_can_view_partner_finance(self.request.user, partner.organization)
        return context


class PayoutCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        partner = get_object_or_404(Partner.objects.select_related("organization"), pk=pk)
        if not user_can_manage_partner_payouts(request.user, partner.organization):
            raise PermissionDenied
        try:
            payout = create_payout(organization=partner.organization, partner=partner, actor=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Paiement {payout.reference} préparé.")
        return redirect("partners:detail", pk=partner.pk)


class PayoutMarkPaidView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        payout = get_object_or_404(PartnerPayout, pk=pk)
        if not user_can_manage_partner_payouts(request.user, payout.organization):
            raise PermissionDenied
        mark_payout_paid(payout=payout, actor=request.user)
        messages.success(request, f"Paiement {payout.reference} marqué payé.")
        return redirect("partners:detail", pk=payout.partner_id)


class PayoutCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        payout = get_object_or_404(PartnerPayout, pk=pk)
        if not user_can_manage_partner_payouts(request.user, payout.organization):
            raise PermissionDenied
        if payout.status == PayoutStatus.PAID:
            raise PermissionDenied("Un paiement déjà payé ne peut pas être annulé.")
        cancel_payout(payout=payout, actor=request.user)
        messages.success(request, f"Paiement {payout.reference} annulé.")
        return redirect("partners:detail", pk=payout.partner_id)

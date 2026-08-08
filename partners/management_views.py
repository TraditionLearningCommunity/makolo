from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import AffiliateCampaignForm
from .management_forms import PartnerUpdateForm
from .models import AffiliateCampaign, Partner, ReferralCode
from .permissions import user_can_manage_partners


class PartnerUpdateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def _partner(self, request, pk):
        partner = get_object_or_404(Partner.objects.select_related("organization", "user"), pk=pk)
        if not user_can_manage_partners(request.user, partner.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier ce partenaire.")
        return partner

    def get(self, request, pk):
        partner = self._partner(request, pk)
        return render(
            request,
            "partners/form.html",
            {
                "form": PartnerUpdateForm(instance=partner),
                "title": f"Modifier {partner.display_name}",
                "organization": partner.organization,
            },
        )

    def post(self, request, pk):
        partner = self._partner(request, pk)
        form = PartnerUpdateForm(request.POST, instance=partner)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = form.linked_user
            instance.full_clean()
            instance.save()
            messages.success(request, "Partenaire mis à jour.")
            return redirect("partners:partner-detail", pk=instance.pk)
        return render(
            request,
            "partners/form.html",
            {"form": form, "title": f"Modifier {partner.display_name}", "organization": partner.organization},
            status=400,
        )


class CampaignUpdateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def _campaign(self, request, pk):
        campaign = get_object_or_404(AffiliateCampaign.objects.select_related("organization", "event"), pk=pk)
        if not user_can_manage_partners(request.user, campaign.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier cette campagne.")
        return campaign

    def get(self, request, pk):
        campaign = self._campaign(request, pk)
        return render(
            request,
            "partners/form.html",
            {
                "form": AffiliateCampaignForm(instance=campaign, organization=campaign.organization),
                "title": f"Modifier {campaign.name}",
                "organization": campaign.organization,
            },
        )

    def post(self, request, pk):
        campaign = self._campaign(request, pk)
        form = AffiliateCampaignForm(request.POST, instance=campaign, organization=campaign.organization)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.organization = campaign.organization
            instance.full_clean()
            instance.save()
            messages.success(request, "Campagne mise à jour.")
            return redirect("partners:campaign-detail", pk=instance.pk)
        return render(
            request,
            "partners/form.html",
            {"form": form, "title": f"Modifier {campaign.name}", "organization": campaign.organization},
            status=400,
        )


class ReferralCodeToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        referral = get_object_or_404(
            ReferralCode.objects.select_related("campaign", "campaign__organization", "partner"),
            pk=pk,
        )
        if not user_can_manage_partners(request.user, referral.campaign.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier ce code ambassadeur.")
        referral.is_active = not referral.is_active
        referral.save(update_fields=["is_active", "updated_at"])
        state = "activé" if referral.is_active else "désactivé"
        messages.success(request, f"Code {referral.code} {state}.")
        return redirect("partners:campaign-detail", pk=referral.campaign_id)

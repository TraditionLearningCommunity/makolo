from django import forms

from crm.models import CommunicationCampaign
from events.models import Event
from loyalty.models import LoyaltyProgram
from partners.models import AffiliateCampaign
from promotions.models import Promotion

from .models import GrowthSpend


class GrowthSpendForm(forms.ModelForm):
    class Meta:
        model = GrowthSpend
        fields = [
            "event",
            "channel",
            "crm_campaign",
            "partner_campaign",
            "promotion",
            "loyalty_program",
            "label",
            "amount",
            "currency",
            "incurred_at",
            "notes",
        ]
        widgets = {
            "incurred_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by(
            "-start_at"
        )
        self.fields["crm_campaign"].queryset = CommunicationCampaign.objects.filter(
            organization=organization
        ).order_by("-created_at")
        self.fields["partner_campaign"].queryset = AffiliateCampaign.objects.filter(
            organization=organization
        ).order_by("-created_at")
        self.fields["promotion"].queryset = Promotion.objects.filter(
            organization=organization
        ).order_by("name")
        self.fields["loyalty_program"].queryset = LoyaltyProgram.objects.filter(
            organization=organization
        )
        self.fields["currency"].widget.attrs.update(
            {"maxlength": "3", "placeholder": "USD"}
        )

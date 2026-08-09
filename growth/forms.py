from django import forms

from crm.models import CommunicationCampaign
from events.models import Event

from .models import EventFeedback, MarketingLink


class MarketingLinkForm(forms.ModelForm):
    class Meta:
        model = MarketingLink
        fields = ["event", "crm_campaign", "name", "channel", "attribution_window_days"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
        self.fields["crm_campaign"].queryset = CommunicationCampaign.objects.filter(
            organization=organization
        ).order_by("-created_at")

    def clean(self):
        cleaned = super().clean()
        self.instance.organization = self.organization
        return cleaned


class EventFeedbackForm(forms.ModelForm):
    class Meta:
        model = EventFeedback
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(value, f"{value}/5") for value in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 5, "maxlength": 2000}),
        }

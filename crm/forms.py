from django import forms

from events.models import Event
from tickets.models import TicketType

from .models import AudienceSegment, CommunicationCampaign


FIELD_CLASS = "mt-1 w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 outline-none focus:border-indigo-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
CHECKBOX_CLASS = "h-5 w-5 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", CHECKBOX_CLASS)
            else:
                field.widget.attrs.setdefault("class", FIELD_CLASS)


class AudienceSegmentForm(StyledModelForm):
    class Meta:
        model = AudienceSegment
        fields = [
            "name",
            "description",
            "event",
            "audience_kind",
            "ticket_type",
            "marketing_consent_only",
            "city",
            "country",
            "is_active",
        ]
        labels = {
            "name": "Nom du segment",
            "description": "Description",
            "event": "Événement",
            "audience_kind": "Audience",
            "ticket_type": "Type de billet",
            "marketing_consent_only": "Uniquement les contacts ayant accepté le marketing",
            "city": "Ville",
            "country": "Pays",
            "is_active": "Segment actif",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
            self.fields["ticket_type"].queryset = TicketType.objects.filter(event__organization=organization).select_related("event").order_by("event__title", "name")
        else:
            self.fields["event"].queryset = Event.objects.none()
            self.fields["ticket_type"].queryset = TicketType.objects.none()


class CommunicationCampaignForm(StyledModelForm):
    scheduled_at = forms.DateTimeField(
        required=False,
        label="Planifier pour",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Laisser vide pour garder le brouillon et l’envoyer manuellement.",
    )

    class Meta:
        model = CommunicationCampaign
        fields = [
            "name",
            "kind",
            "segment",
            "event",
            "subject",
            "preview_text",
            "body",
            "cta_label",
            "cta_url",
        ]
        labels = {
            "name": "Nom interne",
            "kind": "Type de communication",
            "segment": "Segment",
            "event": "Événement associé",
            "subject": "Objet de l’e-mail",
            "preview_text": "Pré-en-tête",
            "body": "Message",
            "cta_label": "Bouton — libellé",
            "cta_url": "Bouton — URL",
        }
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["segment"].queryset = AudienceSegment.objects.filter(organization=organization, is_active=True).order_by("name")
            self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
        else:
            self.fields["segment"].queryset = AudienceSegment.objects.none()
            self.fields["event"].queryset = Event.objects.none()


class CRMContactNoteForm(forms.Form):
    body = forms.CharField(
        label="Note interne",
        widget=forms.Textarea(attrs={"rows": 4, "class": FIELD_CLASS, "placeholder": "Ajouter un contexte utile à l’équipe…"}),
    )


class MarketingConsentForm(forms.Form):
    subscribed = forms.BooleanField(required=False, label="Consentement marketing actif")
    source = forms.CharField(
        required=False,
        max_length=120,
        label="Source du consentement",
        widget=forms.TextInput(attrs={"class": FIELD_CLASS, "placeholder": "Ex. formulaire newsletter du 09/08/2026"}),
    )

    def clean(self):
        data = super().clean()
        if data.get("subscribed") and not (data.get("source") or "").strip():
            self.add_error("source", "Indiquez la source du consentement avant d’abonner le contact.")
        return data

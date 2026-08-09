import json

from django import forms

from events.models import Event
from tickets.models import TicketType

from .models import (
    AudienceSegment,
    CampaignTemplate,
    CommunicationCampaign,
    CRMCustomField,
    CRMTag,
    CustomFieldType,
)


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
    custom_filters = forms.JSONField(
        required=False,
        label="Filtres sur champs personnalisés",
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text='Objet JSON clé/valeur, ex. {"niveau": "vip", "entreprise": "SMNA"}.',
    )

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
            "required_tags",
            "custom_filters",
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
            "required_tags": "Tags obligatoires",
            "is_active": "Segment actif",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
            self.fields["ticket_type"].queryset = TicketType.objects.filter(event__organization=organization).select_related("event").order_by("event__title", "name")
            self.fields["required_tags"].queryset = CRMTag.objects.filter(organization=organization).order_by("name")
        else:
            self.fields["event"].queryset = Event.objects.none()
            self.fields["ticket_type"].queryset = TicketType.objects.none()
            self.fields["required_tags"].queryset = CRMTag.objects.none()


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
            "template",
            "event",
            "subject",
            "preview_text",
            "body",
            "cta_label",
            "cta_url",
            "track_conversions",
            "attribution_window_days",
        ]
        labels = {
            "name": "Nom interne",
            "kind": "Type de communication",
            "segment": "Segment",
            "template": "Modèle réutilisable",
            "event": "Événement associé",
            "subject": "Objet de l’e-mail",
            "preview_text": "Pré-en-tête",
            "body": "Message",
            "cta_label": "Bouton — libellé",
            "cta_url": "Bouton — URL",
            "track_conversions": "Mesurer les clics et les ventes attribuées",
            "attribution_window_days": "Fenêtre d’attribution (jours)",
        }
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["segment"].queryset = AudienceSegment.objects.filter(organization=organization, is_active=True).order_by("name")
            self.fields["template"].queryset = CampaignTemplate.objects.filter(organization=organization, is_active=True).order_by("name")
            self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
        else:
            self.fields["segment"].queryset = AudienceSegment.objects.none()
            self.fields["template"].queryset = CampaignTemplate.objects.none()
            self.fields["event"].queryset = Event.objects.none()


class CampaignTemplateForm(StyledModelForm):
    class Meta:
        model = CampaignTemplate
        fields = ["name", "kind", "subject", "preview_text", "body", "cta_label", "cta_url", "is_active"]
        labels = {
            "name": "Nom du modèle",
            "kind": "Type de communication",
            "subject": "Objet par défaut",
            "preview_text": "Pré-en-tête",
            "body": "Message",
            "cta_label": "Bouton — libellé",
            "cta_url": "Bouton — URL",
            "is_active": "Modèle actif",
        }
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}


class CRMTagForm(StyledModelForm):
    class Meta:
        model = CRMTag
        fields = ["name", "color"]
        labels = {"name": "Nom du tag", "color": "Couleur / identifiant visuel"}


class CRMCustomFieldForm(StyledModelForm):
    options_text = forms.CharField(
        required=False,
        label="Choix possibles",
        help_text="Pour une liste de choix : une option par ligne.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = CRMCustomField
        fields = ["key", "label", "field_type"]
        labels = {"key": "Clé technique", "label": "Libellé", "field_type": "Type"}

    def clean(self):
        data = super().clean()
        if data.get("field_type") == CustomFieldType.SELECT:
            options = [line.strip() for line in (data.get("options_text") or "").splitlines() if line.strip()]
            if not options:
                self.add_error("options_text", "Ajoutez au moins un choix.")
            data["options"] = options
        else:
            data["options"] = []
        return data


class ContactTagForm(forms.Form):
    tag = forms.ModelChoiceField(queryset=CRMTag.objects.none(), label="Tag")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tag"].queryset = CRMTag.objects.filter(organization=organization).order_by("name") if organization else CRMTag.objects.none()
        self.fields["tag"].widget.attrs["class"] = FIELD_CLASS


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

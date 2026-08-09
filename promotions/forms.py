from django import forms
from django.db.models import Q

from crm.models import CommunicationCampaign
from events.models import Event
from tickets.models import TicketType

from .models import Promotion, PromotionCode


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = [
            "name",
            "description",
            "event",
            "discount_type",
            "discount_value",
            "max_discount_amount",
            "min_order_amount",
            "currency",
            "eligible_ticket_types",
            "starts_at",
            "ends_at",
            "max_redemptions",
            "max_redemptions_per_customer",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "eligible_ticket_types": forms.CheckboxSelectMultiple(),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
        labels = {
            "name": "Nom de l'offre",
            "description": "Description interne",
            "event": "Événement",
            "discount_type": "Type de remise",
            "discount_value": "Valeur de la remise",
            "max_discount_amount": "Plafond de remise",
            "min_order_amount": "Commande minimum",
            "currency": "Devise",
            "eligible_ticket_types": "Billets éligibles",
            "starts_at": "Début",
            "ends_at": "Fin",
            "max_redemptions": "Quota global",
            "max_redemptions_per_customer": "Utilisations max par client",
            "is_active": "Offre active",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
        self.fields["eligible_ticket_types"].queryset = TicketType.objects.filter(
            event__organization=organization
        ).select_related("event").order_by("event__start_at", "name")
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        if event and event.organization_id != self.organization.pk:
            self.add_error("event", "Cet événement appartient à une autre organisation.")
        for ticket_type in cleaned.get("eligible_ticket_types") or []:
            if ticket_type.event.organization_id != self.organization.pk:
                self.add_error("eligible_ticket_types", "Un billet appartient à une autre organisation.")
            if event and ticket_type.event_id != event.pk:
                self.add_error("eligible_ticket_types", "Les billets doivent appartenir à l'événement choisi.")
        return cleaned


class PromotionCodeForm(forms.ModelForm):
    class Meta:
        model = PromotionCode
        fields = [
            "code",
            "label",
            "crm_campaign",
            "starts_at",
            "ends_at",
            "max_redemptions",
            "is_private",
            "is_active",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }
        labels = {
            "code": "Code",
            "label": "Libellé public",
            "crm_campaign": "Campagne CRM associée",
            "starts_at": "Début spécifique du code",
            "ends_at": "Fin spécifique du code",
            "max_redemptions": "Quota du code",
            "is_private": "Code privé (ne pas afficher au checkout)",
            "is_active": "Code actif",
        }

    def __init__(self, *args, promotion, **kwargs):
        super().__init__(*args, **kwargs)
        self.promotion = promotion
        campaigns = CommunicationCampaign.objects.filter(organization=promotion.organization)
        if promotion.event_id:
            campaigns = campaigns.filter(Q(event__isnull=True) | Q(event=promotion.event))
        self.fields["crm_campaign"].queryset = campaigns.distinct().order_by("-created_at")
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", INPUT_CLASS)

from django import forms

from crm.models import AudienceSegment, CampaignTemplate, CRMTag
from events.models import Event
from tickets.models import TicketType

from .models import CRMWorkflow, CRMWorkflowAction, EventAutomationPolicy


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)


class EventAutomationPolicyForm(forms.ModelForm):
    class Meta:
        model = EventAutomationPolicy
        fields = [
            "is_active",
            "reminder_7d_enabled",
            "reminder_24h_enabled",
            "reminder_2h_enabled",
            "post_event_followup_enabled",
            "auto_complete_event",
            "auto_close_sales_at_start",
            "capacity_alerts_enabled",
            "capacity_alert_percent",
            "low_stock_alerts_enabled",
            "low_stock_threshold",
        ]
        labels = {
            "is_active": "Activer Makolo Autopilot",
            "reminder_7d_enabled": "Rappel 7 jours avant",
            "reminder_24h_enabled": "Rappel 24 heures avant",
            "reminder_2h_enabled": "Rappel 2 heures avant",
            "post_event_followup_enabled": "Message après l'événement",
            "auto_complete_event": "Terminer automatiquement l'événement après sa fin",
            "auto_close_sales_at_start": "Fermer automatiquement les ventes au démarrage",
            "capacity_alerts_enabled": "Alerter l'équipe quand le remplissage atteint un seuil",
            "capacity_alert_percent": "Seuil de remplissage (%)",
            "low_stock_alerts_enabled": "Alerter l'équipe quand un stock devient faible",
            "low_stock_threshold": "Seuil de stock faible",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = INPUT_CLASS


class CRMWorkflowForm(forms.ModelForm):
    class Meta:
        model = CRMWorkflow
        fields = [
            "name",
            "description",
            "trigger",
            "event",
            "segment",
            "ticket_type",
            "min_order_amount",
            "currency",
            "event_offset_minutes",
            "trigger_grace_minutes",
            "is_active",
        ]
        labels = {
            "name": "Nom du scénario",
            "description": "Description interne",
            "trigger": "Déclencheur",
            "event": "Événement ciblé",
            "segment": "Segment requis",
            "ticket_type": "Type de billet requis",
            "min_order_amount": "Montant minimum de commande",
            "currency": "Devise",
            "event_offset_minutes": "Minutes avant l’événement",
            "trigger_grace_minutes": "Fenêtre de déclenchement (minutes)",
            "is_active": "Scénario actif",
        }
        help_texts = {
            "segment": "Optionnel : le contact doit encore appartenir à ce segment au moment du déclenchement.",
            "event_offset_minutes": "Exemple : 4320 = trois jours avant l’événement.",
            "trigger_grace_minutes": "Évite d’envoyer un rappel devenu trop ancien après une interruption du worker.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at")
            self.fields["segment"].queryset = AudienceSegment.objects.filter(organization=organization, is_active=True).order_by("name")
            self.fields["ticket_type"].queryset = TicketType.objects.filter(event__organization=organization).select_related("event").order_by("event__title", "name")
        else:
            self.fields["event"].queryset = Event.objects.none()
            self.fields["segment"].queryset = AudienceSegment.objects.none()
            self.fields["ticket_type"].queryset = TicketType.objects.none()
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = INPUT_CLASS

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance


class CRMWorkflowActionForm(forms.ModelForm):
    class Meta:
        model = CRMWorkflowAction
        fields = [
            "position",
            "kind",
            "delay_minutes",
            "template",
            "tag",
            "title",
            "message",
            "marketing_action",
            "is_active",
        ]
        labels = {
            "position": "Ordre",
            "kind": "Action",
            "delay_minutes": "Délai après l’étape précédente (minutes)",
            "template": "Modèle e-mail",
            "tag": "Tag CRM",
            "title": "Titre de notification",
            "message": "Message",
            "marketing_action": "Cette notification Makolo est promotionnelle",
            "is_active": "Action active",
        }
        help_texts = {
            "delay_minutes": "0 = immédiatement. 1440 = un jour plus tard.",
            "title": "Utilisé par les notifications contact/équipe.",
            "message": "Variables disponibles : {{ contact.name }}, {{ organization.name }}, {{ event.title }}, {{ event.start_at }}, {{ order.reference }}, {{ order.amount }}, {{ order.currency }}.",
            "marketing_action": "Si activé, Makolo exige le consentement CRM et les préférences marketing de ce compte/organisateur avant d’afficher la notification.",
        }
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, workflow=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow = workflow
        if workflow:
            self.fields["template"].queryset = CampaignTemplate.objects.filter(organization=workflow.organization, is_active=True).order_by("name")
            self.fields["tag"].queryset = CRMTag.objects.filter(organization=workflow.organization).order_by("name")
            if not self.is_bound and not self.instance.pk:
                last_position = workflow.actions.order_by("-position").values_list("position", flat=True).first() or 0
                self.initial.setdefault("position", last_position + 1)
        else:
            self.fields["template"].queryset = CampaignTemplate.objects.none()
            self.fields["tag"].queryset = CRMTag.objects.none()
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = INPUT_CLASS

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.workflow:
            instance.workflow = self.workflow
        if commit:
            instance.save()
        return instance

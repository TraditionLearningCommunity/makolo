from django import forms

from .models import EventAutomationPolicy


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
        input_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
            "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = input_class

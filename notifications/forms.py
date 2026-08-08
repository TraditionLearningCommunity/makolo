from django import forms

from accounts.models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "email_notifications",
            "event_notifications",
            "security_notifications",
            "marketing_notifications",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ]
        widgets = {
            "quiet_hours_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_hours_end": forms.TimeInput(attrs={"type": "time"}),
        }
        labels = {
            "email_notifications": "Recevoir les e-mails Makolo",
            "event_notifications": "Billets, événements et rappels",
            "security_notifications": "Alertes de sécurité",
            "marketing_notifications": "Actualités et communications marketing",
            "quiet_hours_enabled": "Activer les heures silencieuses",
            "quiet_hours_start": "Début des heures silencieuses",
            "quiet_hours_end": "Fin des heures silencieuses",
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("quiet_hours_enabled"):
            if not cleaned.get("quiet_hours_start") or not cleaned.get("quiet_hours_end"):
                raise forms.ValidationError(
                    "Indiquez une heure de début et de fin pour les heures silencieuses."
                )
        return cleaned

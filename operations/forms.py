from django import forms
from django.contrib.auth import get_user_model

from events.models import Event
from organizations.models import OrganizationVerificationStatus

from .models import OperationsIncident


User = get_user_model()


class OperationsIncidentCreateForm(forms.ModelForm):
    class Meta:
        model = OperationsIncident
        fields = [
            "title",
            "category",
            "severity",
            "organization",
            "event",
            "description",
            "assigned_to",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(is_staff=True, is_active=True).order_by("email")
        self.fields["event"].queryset = Event.objects.select_related("organization").order_by("-created_at")


class OperationsIncidentUpdateForm(forms.ModelForm):
    class Meta:
        model = OperationsIncident
        fields = ["status", "severity", "assigned_to", "resolution"]
        widgets = {"resolution": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(is_staff=True, is_active=True).order_by("email")


class OrganizationReviewForm(forms.Form):
    status = forms.ChoiceField(choices=OrganizationVerificationStatus.choices)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), max_length=2000)


class EventModerationForm(forms.Form):
    ACTIONS = [
        ("unlist", "Retirer de la découverte publique"),
        ("private", "Rendre privé"),
        ("cancel", "Annuler l'événement"),
        ("restore_public", "Restaurer la visibilité publique"),
    ]
    action = forms.ChoiceField(choices=ACTIONS)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), max_length=2000)

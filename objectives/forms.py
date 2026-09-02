from django import forms

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from journeys.models import Journey
from organizations.models import Organization

from .models import DossierLifecycle
from .selectors import linkable_journeys_for_profile
from .services import ALLOWED_LIFECYCLE_TRANSITIONS


class DossierCreateForm(forms.Form):
    title = forms.CharField(label="Objectif", max_length=220)
    description = forms.CharField(label="Contexte", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    owning_space = forms.ModelChoiceField(
        label="Espace porteur",
        queryset=Organization.objects.none(),
        required=False,
        help_text="Laissez vide pour un Dossier personnel.",
    )
    deadline = forms.DateField(label="Échéance", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE)
        queryset = Organization.objects.order_by("name")
        if allowed is not None:
            queryset = queryset.filter(pk__in=allowed)
        self.fields["owning_space"].queryset = queryset


class DossierJourneyLinkForm(forms.Form):
    journey = forms.ModelChoiceField(label="Démarche", queryset=Journey.objects.none())

    def __init__(self, *args, actor, dossier, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["journey"].queryset = linkable_journeys_for_profile(actor, dossier=dossier)
        self.fields["journey"].label_from_instance = lambda journey: journey.activity.title


class DossierLifecycleForm(forms.Form):
    lifecycle = forms.ChoiceField(label="État")

    def __init__(self, *args, dossier, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = {dossier.lifecycle, *ALLOWED_LIFECYCLE_TRANSITIONS[dossier.lifecycle]}
        self.fields["lifecycle"].choices = [
            (value, label)
            for value, label in DossierLifecycle.choices
            if value in allowed
        ]
        self.fields["lifecycle"].initial = dossier.lifecycle

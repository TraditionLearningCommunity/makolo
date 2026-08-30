from django import forms
from django.contrib.auth import get_user_model

from journeys.collaboration_models import (
    JourneyAssignmentResponsibility,
    JourneyBlockerCategory,
    JourneyBlockerSeverity,
    JourneyNoteVisibility,
    JourneyStepKind,
)

from .models import (
    CompletionPolicy,
    IntakePolicy,
    OpportunityPolicy,
    ServiceIntakeQuestionType,
    ServiceKind,
)


User = get_user_model()


class ServiceCaseFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="Recherche")
    attention = forms.BooleanField(required=False, label="Seulement les dossiers à traiter")


class ServiceNoteForm(forms.Form):
    body = forms.CharField(label="Note", widget=forms.Textarea(attrs={"rows": 4}), max_length=5000)
    visibility = forms.ChoiceField(label="Visibilité", choices=JourneyNoteVisibility.choices)


class ServiceBlockerForm(forms.Form):
    title = forms.CharField(label="Blocage", max_length=220)
    category = forms.ChoiceField(label="Catégorie", choices=JourneyBlockerCategory.choices)
    severity = forms.ChoiceField(label="Sévérité", choices=JourneyBlockerSeverity.choices)
    description = forms.CharField(label="Détails", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    due_at = forms.DateTimeField(label="Échéance", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))


class ServiceAssignmentForm(forms.Form):
    profile = forms.ModelChoiceField(label="Personne", queryset=User.objects.none())
    responsibility = forms.ChoiceField(label="Responsabilité", choices=JourneyAssignmentResponsibility.choices)
    is_primary = forms.BooleanField(label="Responsable principal", required=False)
    replace_primary = forms.BooleanField(label="Remplacer le responsable principal actif", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = User.objects.filter(is_active=True).order_by("first_name", "last_name", "email", "pk")


class ServiceConfigurationForm(forms.Form):
    service_kind = forms.ChoiceField(label="Type de service", choices=ServiceKind.choices)
    opportunity_policy = forms.ChoiceField(label="Politique Opportunity", choices=OpportunityPolicy.choices)
    intake_policy = forms.ChoiceField(label="Politique Intake", choices=IntakePolicy.choices)
    allows_external_beneficiary = forms.BooleanField(label="Autoriser un bénéficiaire externe", required=False)
    completion_policy = forms.ChoiceField(label="Politique de complétion", choices=CompletionPolicy.choices)


class ServicePlanTemplateForm(forms.Form):
    key = forms.SlugField(label="Clé", max_length=120)
    name = forms.CharField(label="Nom", max_length=220)


class ServiceTemplateStepForm(forms.Form):
    title = forms.CharField(label="Étape", max_length=220)
    kind = forms.ChoiceField(label="Type", choices=JourneyStepKind.choices)
    description = forms.CharField(label="Description", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    position = forms.IntegerField(label="Position", min_value=0, initial=0)
    is_required = forms.BooleanField(label="Obligatoire", required=False, initial=True)
    relative_due_days = forms.IntegerField(label="Échéance relative (jours)", required=False, min_value=0)


class ServiceIntakeQuestionForm(forms.Form):
    key = forms.SlugField(label="Clé", max_length=120)
    prompt = forms.CharField(label="Question", max_length=500)
    question_type = forms.ChoiceField(label="Type", choices=ServiceIntakeQuestionType.choices)
    options = forms.CharField(label="Options (une par ligne)", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    is_required = forms.BooleanField(label="Obligatoire", required=False)
    position = forms.IntegerField(label="Position", min_value=0, initial=0)

    def clean_options(self):
        raw = self.cleaned_data.get("options") or ""
        return [value.strip() for value in raw.splitlines() if value.strip()]


class ServiceReviewDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        label="Décision",
        choices=(("approved", "Approuver"), ("changes_requested", "Demander des modifications")),
    )
    comment = forms.CharField(label="Commentaire", required=False, widget=forms.Textarea(attrs={"rows": 4}))

from django import forms

from .models import (
    Opportunity,
    OpportunityKind,
    OpportunitySourceCheckResult,
    OpportunitySourceType,
    OpportunitySubmissionStatus,
)


class OpportunityCreateForm(forms.Form):
    kind = forms.ChoiceField(label="Type", choices=OpportunityKind.choices)


class OpportunityRevisionForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=240)
    issuer_name = forms.CharField(label="Émetteur", max_length=220)
    summary = forms.CharField(label="Résumé", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    opens_at = forms.DateTimeField(label="Ouverture", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    deadline_at = forms.DateTimeField(label="Échéance", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    timezone_name = forms.CharField(label="Fuseau horaire", initial="Africa/Lubumbashi", max_length=100)
    application_instructions = forms.CharField(label="Instructions", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    remote_allowed = forms.NullBooleanField(label="À distance possible", required=False, widget=forms.Select(choices=(("unknown", "Non précisé"), ("true", "Oui"), ("false", "Non"))))
    change_summary = forms.CharField(label="Résumé des changements", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class OpportunitySourceForm(forms.Form):
    source_type = forms.ChoiceField(label="Type de source", choices=OpportunitySourceType.choices)
    source_name = forms.CharField(label="Source", max_length=220)
    url = forms.URLField(label="URL", max_length=1000)
    external_reference = forms.CharField(label="Référence externe", required=False, max_length=240)
    is_primary = forms.BooleanField(label="Source principale", required=False)
    verified = forms.BooleanField(label="Source déjà vérifiée", required=False)


class OpportunitySourceCheckForm(forms.Form):
    result = forms.ChoiceField(label="Résultat", choices=OpportunitySourceCheckResult.choices)
    note = forms.CharField(label="Note de vérification", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class OpportunitySubmissionDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        label="Décision",
        choices=(
            (OpportunitySubmissionStatus.ACCEPTED, "Accepter"),
            (OpportunitySubmissionStatus.REJECTED, "Rejeter"),
            (OpportunitySubmissionStatus.DUPLICATE, "Doublon"),
        ),
    )
    resolved_opportunity = forms.ModelChoiceField(
        label="Opportunity canonique",
        queryset=Opportunity.objects.none(),
        required=False,
        empty_label="Aucune",
    )
    review_note = forms.CharField(label="Note de revue", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resolved_opportunity"].queryset = Opportunity.objects.exclude(publication_status="merged").select_related("current_revision").order_by("-created_at")


class OpportunityMergeForm(forms.Form):
    duplicate = forms.ModelChoiceField(
        label="Opportunity à fusionner dans celle-ci",
        queryset=Opportunity.objects.none(),
        empty_label="Choisir un doublon",
    )

    def __init__(self, *args, canonical=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Opportunity.objects.exclude(publication_status="merged").select_related("current_revision").order_by("-created_at")
        if canonical is not None:
            queryset = queryset.exclude(pk=canonical.pk)
        self.fields["duplicate"].queryset = queryset

from django import forms

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactStatus


class ParticipantArtifactUploadForm(forms.Form):
    title = forms.CharField(label="Nom du document", max_length=220)
    kind = forms.ChoiceField(label="Type de document", choices=JourneyArtifactKind.choices)
    step = forms.ModelChoiceField(label="Étape liée", queryset=None, required=False, empty_label="Aucune étape")
    file = forms.FileField(label="Fichier")

    def __init__(self, *args, journey, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["step"].queryset = journey.steps.order_by("position", "created_at", "id")


class ParticipantArtifactVersionForm(forms.Form):
    file = forms.FileField(label="Nouvelle version du fichier")


class ExternalPaymentEvidenceForm(forms.Form):
    file = forms.FileField(label="Preuve de paiement")
    paid_at = forms.DateTimeField(
        label="Date et heure du paiement",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    external_reference = forms.CharField(label="Référence externe", max_length=240, required=False)


ARTIFACT_SUBMITTED_STATUS = JourneyArtifactStatus.SUBMITTED

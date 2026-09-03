from django import forms

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity


class PersonalAssetCreateForm(forms.Form):
    title = forms.CharField(max_length=220, label="Titre")
    kind = forms.ChoiceField(choices=JourneyArtifactKind.choices, label="Type")
    sensitivity = forms.ChoiceField(choices=JourneyArtifactSensitivity.choices, label="Sensibilité")
    issued_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’émission")
    expires_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’expiration")
    file = forms.FileField(label="Document")


class PersonalAssetVersionForm(forms.Form):
    issued_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’émission")
    expires_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’expiration")
    file = forms.FileField(label="Nouvelle version")


class SaveArtifactToLibraryForm(forms.Form):
    MODE_NEW = "new"
    MODE_EXISTING = "existing"
    mode = forms.ChoiceField(choices=((MODE_NEW, "Créer un nouvel élément"), (MODE_EXISTING, "Ajouter comme nouvelle version")), initial=MODE_NEW, widget=forms.RadioSelect)
    title = forms.CharField(max_length=220, required=False, label="Titre")
    kind = forms.ChoiceField(choices=JourneyArtifactKind.choices, required=False, label="Type")
    existing_asset_id = forms.UUIDField(required=False, label="Élément existant")
    issued_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’émission")
    expires_at = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date d’expiration")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") == self.MODE_EXISTING and not cleaned.get("existing_asset_id"):
            self.add_error("existing_asset_id", "Choisissez un élément existant.")
        return cleaned

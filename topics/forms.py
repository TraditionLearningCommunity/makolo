from django import forms

from .models import OpenToKind, ProfileInterest, Topic


class InterestSelectionForm(forms.Form):
    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, label="Centres d’intérêt")
    public_topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, label="Centres d’intérêt publics")

    def __init__(self, *args, **kwargs):
        profile = kwargs.pop("profile", None)
        super().__init__(*args, **kwargs)
        active = Topic.objects.filter(is_active=True).order_by("label", "code")
        self.fields["topics"].queryset = active
        self.fields["public_topics"].queryset = active.filter(profile_interests__profile=profile).distinct() if profile else Topic.objects.none()

    def clean(self):
        cleaned = super().clean()
        selected = set(cleaned.get("topics", []))
        public = set(cleaned.get("public_topics", []))
        if not public.issubset(selected):
            self.add_error("public_topics", "Un centre d’intérêt public doit aussi rester sélectionné.")
        return cleaned


class OpenToSettingsForm(forms.Form):
    kinds = forms.MultipleChoiceField(required=False, choices=OpenToKind.choices, widget=forms.CheckboxSelectMultiple, label="Ouvert à")
    public_kinds = forms.MultipleChoiceField(required=False, choices=OpenToKind.choices, widget=forms.CheckboxSelectMultiple, label="Afficher publiquement")
    searchable_kinds = forms.MultipleChoiceField(required=False, choices=OpenToKind.choices, widget=forms.CheckboxSelectMultiple, label="Utilisable pour la découverte future")

    def clean(self):
        cleaned = super().clean()
        kinds = set(cleaned.get("kinds", []))
        if not set(cleaned.get("public_kinds", [])).issubset(kinds):
            self.add_error("public_kinds", "Activez d’abord cette préférence « Ouvert à ».")
        if not set(cleaned.get("searchable_kinds", [])).issubset(kinds):
            self.add_error("searchable_kinds", "Activez d’abord cette préférence « Ouvert à ».")
        return cleaned

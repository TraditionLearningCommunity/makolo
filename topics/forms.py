from django import forms

from .models import Topic


class InterestSelectionForm(forms.Form):
    topics = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Centres d’intérêt",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topics"].queryset = Topic.objects.filter(is_active=True).order_by("label", "code")

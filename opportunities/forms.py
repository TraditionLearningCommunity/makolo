from django import forms


class OpportunitySubmissionForm(forms.Form):
    url = forms.URLField(label="Lien de l’opportunité", max_length=1000)
    title = forms.CharField(label="Titre", max_length=240, required=False)
    comment = forms.CharField(label="Commentaire", required=False, widget=forms.Textarea(attrs={"rows": 4}))

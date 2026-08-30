from django import forms

from opportunities.selectors import published_opportunities

from .models import OpportunityPolicy, ServiceIntakeQuestionType


class ServiceStartForm(forms.Form):
    objective = forms.CharField(label="Votre objectif", required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 4}))
    opportunity = forms.ModelChoiceField(label="Opportunité", queryset=published_opportunities(), required=False, empty_label="Choisir une opportunité")

    def __init__(self, *args, service, initial_opportunity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = service
        if service.opportunity_policy == OpportunityPolicy.NONE:
            self.fields.pop("opportunity")
        else:
            self.fields["opportunity"].required = service.opportunity_policy == OpportunityPolicy.REQUIRED
            if initial_opportunity is not None:
                self.fields["opportunity"].initial = initial_opportunity


class ServiceIntakeForm(forms.Form):
    def __init__(self, *args, questions, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = list(questions)
        for question in self.questions:
            key = f"question_{question.pk}"
            common = {"label": question.prompt, "required": False}
            if question.question_type == ServiceIntakeQuestionType.SHORT_TEXT:
                field = forms.CharField(max_length=500, **common)
            elif question.question_type == ServiceIntakeQuestionType.LONG_TEXT:
                field = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), **common)
            elif question.question_type == ServiceIntakeQuestionType.BOOLEAN:
                field = forms.ChoiceField(choices=(("", "Choisir"), ("yes", "Oui"), ("no", "Non")), **common)
            elif question.question_type == ServiceIntakeQuestionType.DATE:
                field = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **common)
            elif question.question_type == ServiceIntakeQuestionType.SINGLE_CHOICE:
                field = forms.ChoiceField(choices=(("", "Choisir"),) + tuple((value, value) for value in question.options), **common)
            else:
                field = forms.MultipleChoiceField(choices=tuple((value, value) for value in question.options), widget=forms.CheckboxSelectMultiple, **common)
            self.fields[key] = field

    def clean(self):
        cleaned = super().clean()
        values = {}
        for question in self.questions:
            key = f"question_{question.pk}"
            value = cleaned.get(key)
            missing = value in (None, "", [])
            if question.is_required and missing:
                self.add_error(key, "Cette réponse est obligatoire.")
                continue
            if missing:
                continue
            if question.question_type == ServiceIntakeQuestionType.BOOLEAN:
                value = value == "yes"
            elif question.question_type == ServiceIntakeQuestionType.DATE:
                value = value.isoformat()
            values[question.pk] = value
        cleaned["intake_values"] = values
        return cleaned

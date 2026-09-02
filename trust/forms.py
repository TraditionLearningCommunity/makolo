from django import forms

from .models import FeedbackAnswer, FeedbackSentiment, ReportCategory, VerificationClaimType


class VerificationRequestForm(forms.Form):
    claim_type = forms.ChoiceField(choices=VerificationClaimType.choices)
    evidence = forms.FileField(required=False)


class VerificationDecisionForm(forms.Form):
    action = forms.ChoiceField(choices=(("review", "Passer en revue"), ("verify", "Vérifier"), ("reject", "Rejeter"), ("revoke", "Révoquer")))
    reason_code = forms.SlugField(required=False, max_length=80)
    private_note = forms.CharField(required=False, widget=forms.Textarea, max_length=3000)
    valid_until = forms.DateTimeField(required=False)


class FeedbackForm(forms.Form):
    delivery = forms.ChoiceField(choices=FeedbackAnswer.choices, required=False, initial=FeedbackAnswer.NOT_APPLICABLE)
    timeliness = forms.ChoiceField(choices=FeedbackAnswer.choices, required=False, initial=FeedbackAnswer.NOT_APPLICABLE)
    access_experience = forms.ChoiceField(choices=FeedbackAnswer.choices, required=False, initial=FeedbackAnswer.NOT_APPLICABLE)
    accuracy = forms.ChoiceField(choices=FeedbackAnswer.choices, required=False, initial=FeedbackAnswer.NOT_APPLICABLE)
    overall_sentiment = forms.ChoiceField(choices=(("", "Sans opinion"), *FeedbackSentiment.choices), required=False)
    comment = forms.CharField(required=False, widget=forms.Textarea, max_length=3000)


class ReportForm(forms.Form):
    category = forms.ChoiceField(choices=ReportCategory.choices)
    description = forms.CharField(widget=forms.Textarea, max_length=5000)
    evidence = forms.FileField(required=False)


class ReportStaffForm(forms.Form):
    action = forms.ChoiceField(choices=(("triage", "Trier"), ("investigate", "Investiguer"), ("resolve", "Résoudre"), ("dismiss", "Classer sans suite"), ("dispute", "Ouvrir un litige")))
    resolution_code = forms.SlugField(required=False, max_length=80)
    private_note = forms.CharField(required=False, widget=forms.Textarea, max_length=3000)


class DisputeStaffForm(forms.Form):
    action = forms.ChoiceField(choices=(("request_info", "Demander une information"), ("decide", "Décider"), ("close", "Clore")))
    decision_code = forms.SlugField(required=False, max_length=80)
    decision_summary = forms.CharField(required=False, widget=forms.Textarea, max_length=3000)
    remedy_code = forms.ChoiceField(required=False, choices=(("no_action", "Aucune action"), ("operator_action_required", "Action opérateur requise"), ("access_reissue_requested", "Réémission d’accès demandée"), ("correction_required", "Correction requise"), ("refund_requested", "Remboursement demandé"), ("other", "Autre")))
    private_note = forms.CharField(required=False, widget=forms.Textarea, max_length=3000)

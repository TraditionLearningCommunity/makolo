from django import forms
from django.conf import settings

from .models import PaymentMethod, PaymentProvider


class ObligationPaymentStartForm(forms.Form):
    provider = forms.ChoiceField(label="Service de paiement", choices=())
    method = forms.ChoiceField(label="Mode de paiement", choices=PaymentMethod.choices)
    payer_name = forms.CharField(label="Nom", max_length=180, required=False)
    payer_email = forms.EmailField(label="E-mail", required=False)
    payer_phone = forms.CharField(label="Téléphone", max_length=40, required=False)

    def __init__(self, *args, obligation=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        if getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
            choices.append((PaymentProvider.SANDBOX, PaymentProvider.SANDBOX.label))
        if user and getattr(user, "is_staff", False):
            choices.append((PaymentProvider.MANUAL, PaymentProvider.MANUAL.label))
        self.fields["provider"].choices = choices
        if len(choices) == 1:
            self.fields["provider"].initial = choices[0][0]
            self.fields["provider"].widget = forms.HiddenInput()
        beneficiary = getattr(getattr(obligation, "journey", None), "beneficiary", None)
        if beneficiary:
            self.fields["payer_name"].initial = getattr(beneficiary, "full_name", "") or getattr(beneficiary, "username", "")
            self.fields["payer_email"].initial = getattr(beneficiary, "email", "")

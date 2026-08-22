from django import forms
from django.conf import settings

from events.permissions import user_can_manage_event

from .models import PaymentMethod, PaymentProvider


class PaymentStartForm(forms.Form):
    provider = forms.ChoiceField(choices=PaymentProvider.choices)
    method = forms.ChoiceField(choices=PaymentMethod.choices)
    payer_name = forms.CharField(max_length=180, required=False)
    payer_email = forms.EmailField(required=False)
    payer_phone = forms.CharField(max_length=40, required=False)

    def __init__(self, *args, order=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.user = user
        provider_choices = []
        if getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
            provider_choices.append(
                (PaymentProvider.SANDBOX, PaymentProvider.SANDBOX.label)
            )
        if order and user and user_can_manage_event(user, order.event):
            provider_choices.append(
                (PaymentProvider.MANUAL, PaymentProvider.MANUAL.label)
            )
        self.fields["provider"].choices = provider_choices
        if order:
            self.fields["payer_name"].initial = order.customer_name
            self.fields["payer_email"].initial = order.customer_email


class CommercePaymentStartForm(forms.Form):
    provider = forms.ChoiceField(choices=PaymentProvider.choices)
    method = forms.ChoiceField(choices=PaymentMethod.choices)
    payer_name = forms.CharField(max_length=180, required=False)
    payer_email = forms.EmailField(required=False)
    payer_phone = forms.CharField(max_length=40, required=False)

    def __init__(self, *args, order=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        self.user = user
        provider_choices = []
        if getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
            provider_choices.append((PaymentProvider.SANDBOX, PaymentProvider.SANDBOX.label))
        if user and getattr(user, "is_staff", False):
            provider_choices.append((PaymentProvider.MANUAL, PaymentProvider.MANUAL.label))
        self.fields["provider"].choices = provider_choices
        buyer = getattr(order, "buyer", None)
        if buyer:
            self.fields["payer_name"].initial = (
                getattr(buyer, "full_name", "") or getattr(buyer, "username", "")
            )
            self.fields["payer_email"].initial = getattr(buyer, "email", "")


class ManualPaymentCompleteForm(forms.Form):
    provider_reference = forms.CharField(max_length=160, required=False)


class RefundForm(forms.Form):
    reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

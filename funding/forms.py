from django import forms
from django.db.models import Q

from activities.models import ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import FundingDetails


def _space_ids_intersection(actor):
    activity_ids = space_ids_with_permission(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE)
    finance_ids = space_ids_with_permission(actor, PermissionCode.FINANCE_MANAGE)
    if activity_ids is None and finance_ids is None:
        return None
    if activity_ids is None:
        return set(finance_ids or [])
    if finance_ids is None:
        return set(activity_ids or [])
    return set(activity_ids) & set(finance_ids)


class FundingConfigurationForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=220)
    short_description = forms.CharField(label="Résumé", max_length=320, required=False)
    description = forms.CharField(label="Pourquoi ce financement ?", required=False, widget=forms.Textarea(attrs={"rows": 5}))
    space = forms.ModelChoiceField(
        label="Espace porteur",
        queryset=Organization.objects.none(),
        required=False,
        help_text="Laissez vide pour un financement personnel.",
    )
    currency = forms.CharField(label="Devise", max_length=3, initial="USD")
    target_amount = forms.DecimalField(label="Objectif", max_digits=12, decimal_places=2, min_value=0.01, required=False)
    minimum_contribution = forms.DecimalField(label="Contribution minimale", max_digits=12, decimal_places=2, min_value=0.01, required=False)
    maximum_contribution = forms.DecimalField(label="Contribution maximale", max_digits=12, decimal_places=2, min_value=0.01, required=False)
    opens_at = forms.DateTimeField(label="Ouverture", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    closes_at = forms.DateTimeField(label="Clôture", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    status = forms.ChoiceField(label="État", choices=ActivityStatus.choices, initial=ActivityStatus.DRAFT)
    visibility = forms.ChoiceField(label="Visibilité", choices=ActivityVisibility.choices, initial=ActivityVisibility.PUBLIC)

    def __init__(self, *args, actor, funding: FundingDetails | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.funding = funding
        allowed_ids = _space_ids_intersection(actor)
        spaces = Organization.objects.order_by("name")
        if allowed_ids is not None:
            spaces = spaces.filter(pk__in=allowed_ids)
        self.fields["space"].queryset = spaces
        if funding is not None:
            activity = funding.activity
            self.fields["space"].disabled = True
            self.initial.update(
                {
                    "title": activity.title,
                    "short_description": activity.short_description,
                    "description": activity.description,
                    "space": activity.space,
                    "currency": funding.currency,
                    "target_amount": funding.target_amount,
                    "minimum_contribution": funding.minimum_contribution,
                    "maximum_contribution": funding.maximum_contribution,
                    "opens_at": funding.opens_at,
                    "closes_at": funding.closes_at,
                    "status": activity.status,
                    "visibility": activity.visibility,
                }
            )

    def clean_currency(self):
        currency = (self.cleaned_data["currency"] or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise forms.ValidationError("Utilisez un code devise de trois lettres, par exemple USD ou EUR.")
        return currency

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get("minimum_contribution")
        maximum = cleaned.get("maximum_contribution")
        opens_at = cleaned.get("opens_at")
        closes_at = cleaned.get("closes_at")
        if minimum is not None and maximum is not None and maximum < minimum:
            self.add_error("maximum_contribution", "Le maximum ne peut pas être inférieur au minimum.")
        if opens_at and closes_at and closes_at < opens_at:
            self.add_error("closes_at", "La clôture doit être postérieure à l’ouverture.")
        return cleaned


class FundingContributionForm(forms.Form):
    amount = forms.DecimalField(label="Montant", max_digits=12, decimal_places=2, min_value=0.01)

    def __init__(self, *args, funding: FundingDetails, **kwargs):
        super().__init__(*args, **kwargs)
        self.funding = funding
        self.fields["amount"].help_text = f"Montant en {funding.currency}."
        if funding.minimum_contribution is not None:
            self.fields["amount"].min_value = funding.minimum_contribution
        if funding.maximum_contribution is not None:
            self.fields["amount"].max_value = funding.maximum_contribution

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.funding.minimum_contribution is not None and amount < self.funding.minimum_contribution:
            raise forms.ValidationError(f"La contribution minimale est de {self.funding.minimum_contribution} {self.funding.currency}.")
        if self.funding.maximum_contribution is not None and amount > self.funding.maximum_contribution:
            raise forms.ValidationError(f"La contribution maximale est de {self.funding.maximum_contribution} {self.funding.currency}.")
        return amount

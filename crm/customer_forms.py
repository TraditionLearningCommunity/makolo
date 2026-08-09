from django import forms

from .customer360 import (
    BEHAVIOR_FILTER_KEY,
    merge_behavior_filters,
    segment_behavior_filters,
    validate_behavior_filters,
)
from .forms import AudienceSegmentForm


class BehavioralSegmentForm(AudienceSegmentForm):
    min_confirmed_orders = forms.IntegerField(
        required=False,
        min_value=0,
        label="Commandes confirmées minimum",
        help_text="Ex. 2 pour cibler les clients récurrents.",
    )
    max_days_since_last_order = forms.IntegerField(
        required=False,
        min_value=0,
        label="Dernier achat il y a au maximum (jours)",
        help_text="Ex. 90 pour les clients actifs des 90 derniers jours.",
    )
    min_days_since_last_order = forms.IntegerField(
        required=False,
        min_value=0,
        label="Dernier achat il y a au minimum (jours)",
        help_text="Ex. 180 pour cibler des clients à réactiver.",
    )
    min_attended_events = forms.IntegerField(
        required=False,
        min_value=0,
        label="Événements fréquentés minimum",
        help_text="Compte les événements où au moins un billet a été scanné.",
    )
    min_promotion_redemptions = forms.IntegerField(
        required=False,
        min_value=0,
        label="Codes promo convertis minimum",
    )
    min_partner_referred_orders = forms.IntegerField(
        required=False,
        min_value=0,
        label="Achats attribués à un partenaire minimum",
    )
    min_spend_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label="Dépense confirmée minimum",
        help_text="Le montant n'est jamais mélangé entre plusieurs devises.",
    )
    spend_currency = forms.CharField(
        required=False,
        max_length=3,
        label="Devise de la dépense",
        help_text="Code ISO à trois lettres, ex. USD ou CDF.",
    )

    behavior_field_names = (
        "min_confirmed_orders",
        "max_days_since_last_order",
        "min_days_since_last_order",
        "min_attended_events",
        "min_promotion_redemptions",
        "min_partner_referred_orders",
        "min_spend_amount",
        "spend_currency",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        behavior = segment_behavior_filters(self.instance) if getattr(self.instance, "pk", None) else {}
        if not self.is_bound:
            custom_filters = dict(getattr(self.instance, "custom_filters", {}) or {})
            custom_filters.pop(BEHAVIOR_FILTER_KEY, None)
            self.initial["custom_filters"] = custom_filters
            self.fields["custom_filters"].initial = custom_filters
            for name in self.behavior_field_names:
                if name in behavior:
                    self.initial[name] = behavior[name]
                    self.fields[name].initial = behavior[name]

    def clean(self):
        cleaned = super().clean()
        raw_behavior = {
            name: cleaned.get(name)
            for name in self.behavior_field_names
            if cleaned.get(name) not in (None, "")
        }
        if raw_behavior.get("spend_currency"):
            raw_behavior["spend_currency"] = raw_behavior["spend_currency"].strip().upper()
        try:
            behavior = validate_behavior_filters(raw_behavior)
        except ValueError as exc:
            self.add_error(None, str(exc))
            return cleaned
        cleaned["custom_filters"] = merge_behavior_filters(
            cleaned.get("custom_filters") or {},
            behavior,
        )
        return cleaned

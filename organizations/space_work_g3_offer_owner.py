"""MT5 Offer owner authoring: one form, two clients, existing Commerce services."""
from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.services import create_offer, update_offer

from .api.space_work_projection import build_space_work_projection


class SpaceOfferOwnerForm(forms.Form):
    name = forms.CharField(label="Nom de l'offre", max_length=180)
    description = forms.CharField(
        label="Description", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )
    unit_price = forms.DecimalField(
        label="Prix unitaire", min_value=0, max_digits=12, decimal_places=2,
    )
    currency = forms.CharField(label="Devise ISO", max_length=3, min_length=3)
    payment_mode = forms.ChoiceField(label="Mode de paiement", choices=PaymentMode.choices)
    min_quantity = forms.IntegerField(label="Quantité minimum", min_value=1)
    max_quantity = forms.IntegerField(
        label="Quantité maximum", min_value=1, required=False,
    )
    status = forms.ChoiceField(
        label="État de l'offre", choices=OfferStatus.choices, required=False,
    )

    def clean_currency(self):
        raw = self.cleaned_data["currency"].strip().upper()
        if len(raw) != 3 or not raw.isalpha():
            raise forms.ValidationError("La devise exige trois lettres.")
        return raw

    def clean(self):
        values = super().clean()
        price, mode = values.get("unit_price"), values.get("payment_mode")
        if price is not None and mode:
            if price == 0 and mode != PaymentMode.NONE:
                self.add_error("payment_mode", "Une offre gratuite utilise le mode sans paiement.")
            if price > 0 and mode == PaymentMode.NONE:
                self.add_error("payment_mode", "Une offre payante exige un mode de paiement.")
        if values.get("min_quantity") and values.get("max_quantity") and (
            values["max_quantity"] < values["min_quantity"]
        ):
            self.add_error("max_quantity", "Le maximum doit être >= au minimum.")
        return values


def offer_owner_scope(*, profile, space, responsibility, activity_id=None,
                      offer_id=None):
    """A permission AND a live Work selection are required; no Space membership grant."""
    if bool(activity_id) == bool(offer_id):
        raise Http404
    offer = None
    if offer_id:
        offer = (
            Offer.objects.filter(pk=offer_id, activity__space=space)
            .select_related("activity").first()
        )
        if offer is None:
            raise Http404
        activity = offer.activity
        source_kind, source_id = "offer", offer.pk
    else:
        activity = Activity.objects.filter(pk=activity_id, space=space).first()
        if activity is None:
            raise Http404
        source_kind, source_id = "activity", activity.pk

    if not can(profile, PermissionCode.ACTIVITY_COMMERCE_MANAGE, activity=activity):
        raise PermissionDenied("La gestion Commerce de cette Activity est nécessaire.")
    selection = build_space_work_projection(
        profile=profile, space=space, responsibility_key=responsibility,
        source_kind=source_kind, source_id=str(source_id),
    )
    if not (selection or {}).get("selection"):
        raise Http404
    return activity, offer


@transaction.atomic
def write_offer(*, activity, offer, cleaned):
    values = {
        "name": cleaned["name"],
        "description": cleaned["description"],
        "unit_price": cleaned["unit_price"],
        "currency": cleaned["currency"],
        "payment_mode": cleaned["payment_mode"],
        "min_quantity": cleaned["min_quantity"],
        "max_quantity": cleaned["max_quantity"],
    }
    if offer is None:
        return create_offer(
            activity=activity, status=OfferStatus.DRAFT,
            payment_modes=[cleaned["payment_mode"]], **values,
        )
    values["status"] = cleaned["status"] or offer.status
    # Editing the default mode must not silently erase other modes the
    # Commerce owner already configured. An actual change of default is
    # explicit and replaces the incompatible set through the canonical API.
    payment_modes = (
        None if cleaned["payment_mode"] == offer.payment_mode
        else [cleaned["payment_mode"]]
    )
    return update_offer(
        offer=offer, payment_modes=payment_modes, **values,
    )


def initial_offer(offer):
    if offer is None:
        return {
            "unit_price": "0.00", "currency": "USD",
            "payment_mode": PaymentMode.NONE,
            "min_quantity": 1, "status": OfferStatus.DRAFT,
        }
    return {
        "name": offer.name,
        "description": offer.description,
        "unit_price": offer.unit_price,
        "currency": offer.currency,
        "payment_mode": offer.payment_mode,
        "min_quantity": offer.min_quantity,
        "max_quantity": offer.max_quantity,
        "status": offer.status,
    }

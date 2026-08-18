"""Compatibility writes for TicketType after Offer/Capacity cutover.

The historical attributes remain Python projections only. This adapter sends
all mutations to the canonical Offer and CapacityPool records.
"""

from django.db import transaction

from commerce.models import OfferStatus, PaymentMode

from .models import TicketType


_OFFER_FIELDS = {
    "price": "unit_price",
    "currency": "currency",
    "sales_start_at": "available_from",
    "sales_end_at": "available_until",
    "min_per_order": "min_quantity",
    "max_per_order": "max_quantity",
}
_LEGACY_FIELDS = frozenset((*_OFFER_FIELDS, "quantity_total", "is_active"))


def _pending(instance):
    return instance.__dict__.setdefault("_legacy_ticket_type_values", {})


def _dirty(instance):
    return instance.__dict__.setdefault("_legacy_ticket_type_dirty", set())


def _offer_property(name, canonical):
    original = getattr(TicketType, name)

    def getter(instance):
        if name in _pending(instance):
            return _pending(instance)[name]
        return original.fget(instance)

    def setter(instance, value):
        if name == "currency" and value:
            value = str(value).upper()
        _pending(instance)[name] = value
        _dirty(instance).add(name)
        if instance.offer_id:
            setattr(instance.offer, canonical, value)

    return property(getter, setter, doc=original.__doc__)


def _quantity_property():
    original = TicketType.quantity_total

    def getter(instance):
        if "quantity_total" in _pending(instance):
            return _pending(instance)["quantity_total"]
        return original.fget(instance)

    def setter(instance, value):
        _pending(instance)["quantity_total"] = value
        _dirty(instance).add("quantity_total")
        if instance.capacity_pool_id:
            instance.capacity_pool.total_quantity = value

    return property(getter, setter, doc=original.__doc__)


def _active_property():
    original = TicketType.is_active

    def getter(instance):
        if "is_active" in _pending(instance):
            return bool(_pending(instance)["is_active"])
        return original.fget(instance)

    def setter(instance, value):
        value = bool(value)
        _pending(instance)["is_active"] = value
        _dirty(instance).add("is_active")
        if instance.offer_id:
            instance.offer.status = OfferStatus.ACTIVE if value else OfferStatus.INACTIVE
        if instance.capacity_pool_id:
            instance.capacity_pool.is_active = value

    return property(getter, setter, doc=original.__doc__)


def install_ticket_type_legacy_compat():
    if getattr(TicketType, "_legacy_compat_installed", False):
        return

    original_init = TicketType.__init__
    original_save = TicketType.save

    for legacy, canonical in _OFFER_FIELDS.items():
        setattr(TicketType, legacy, _offer_property(legacy, canonical))
    TicketType.quantity_total = _quantity_property()
    TicketType.is_active = _active_property()

    def compat_init(instance, *args, **kwargs):
        legacy_values = {name: kwargs.pop(name) for name in tuple(kwargs) if name in _LEGACY_FIELDS}
        original_init(instance, *args, **kwargs)
        instance.__dict__["_legacy_ticket_type_values"] = legacy_values
        instance.__dict__["_legacy_ticket_type_dirty"] = set(legacy_values)

    @transaction.atomic
    def compat_save(instance, *args, **kwargs):
        update_fields = kwargs.pop("update_fields", None)
        requested = set(update_fields or ())
        dirty = _dirty(instance)
        pending = _pending(instance)
        legacy_to_persist = dirty if update_fields is None else dirty & requested

        offer_updates = []
        for legacy, canonical in _OFFER_FIELDS.items():
            if legacy not in legacy_to_persist or not instance.offer_id:
                continue
            value = pending.get(legacy, getattr(instance.offer, canonical))
            setattr(instance.offer, canonical, value)
            offer_updates.append(canonical)
        if "price" in legacy_to_persist and instance.offer_id:
            instance.offer.payment_mode = PaymentMode.NONE if instance.offer.unit_price == 0 else PaymentMode.UPFRONT
            offer_updates.append("payment_mode")
        if "is_active" in legacy_to_persist and instance.offer_id:
            instance.offer.status = OfferStatus.ACTIVE if pending.get("is_active") else OfferStatus.INACTIVE
            offer_updates.append("status")
        if offer_updates:
            instance.offer.save(update_fields=[*dict.fromkeys(offer_updates), "updated_at"])

        pool_updates = []
        if "quantity_total" in legacy_to_persist and instance.capacity_pool_id:
            instance.capacity_pool.total_quantity = pending.get("quantity_total")
            pool_updates.append("total_quantity")
        if "is_active" in legacy_to_persist and instance.capacity_pool_id:
            instance.capacity_pool.is_active = bool(pending.get("is_active"))
            pool_updates.append("is_active")
        if pool_updates:
            instance.capacity_pool.save(update_fields=[*dict.fromkeys(pool_updates), "updated_at"])

        if update_fields is not None:
            own_fields = [field for field in update_fields if field not in _LEGACY_FIELDS]
            if not instance._state.adding and not own_fields:
                dirty.difference_update(legacy_to_persist)
                return None
            kwargs["update_fields"] = own_fields

        result = original_save(instance, *args, **kwargs)
        dirty.difference_update(legacy_to_persist)
        return result

    TicketType.__init__ = compat_init
    TicketType.save = compat_save
    TicketType._legacy_compat_installed = True

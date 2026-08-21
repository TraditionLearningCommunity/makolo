from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import models

TZ = ZoneInfo("Africa/Lubumbashi")
NAMESPACE = uuid.UUID("5b6b4558-2b73-45c0-bdb4-b2a279b2560b")
SEED_TAG = "makolo-demo-2024-2027"

SCALE = {
    "beta": {"users": 8, "orders_per_event": 0},
    "small": {"users": 36, "orders_per_event": 5},
    "medium": {"users": 90, "orders_per_event": 10},
    "large": {"users": 180, "orders_per_event": 18},
}


def stable_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def stable_token(key: str, length: int = 16) -> str:
    return hashlib.sha256(f"{SEED_TAG}:{key}".encode()).hexdigest()[:length]


def dt(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def backdate(obj: models.Model, **values: Any) -> None:
    obj.__class__.objects.filter(pk=obj.pk).update(**values)
    for key, value in values.items():
        setattr(obj, key, value)


def _reuse_business_created_object(model: type[models.Model], defaults: dict[str, Any]):
    if model._meta.label_lower == "crm.crmcontact":
        organization = defaults.get("organization")
        email = (defaults.get("email") or "").strip().lower()
        if organization and email:
            return model.objects.filter(organization=organization, email__iexact=email).first()
    return None


def _same_value(current: Any, expected: Any) -> bool:
    if isinstance(current, models.Model) or isinstance(expected, models.Model):
        if not isinstance(current, models.Model) or not isinstance(expected, models.Model):
            return False
        return current._meta.label_lower == expected._meta.label_lower and current.pk == expected.pk
    return current == expected


def _apply_defaults_if_changed(obj: models.Model, defaults: dict[str, Any]) -> models.Model:
    changed = False
    for field, value in defaults.items():
        current = getattr(obj, field)
        if _same_value(current, value):
            continue
        setattr(obj, field, value)
        changed = True
    if changed:
        obj.save()
    return obj


def upsert(model: type[models.Model], key: str, *, defaults: dict[str, Any]) -> models.Model:
    pk = stable_uuid(f"{model._meta.label_lower}:{key}")
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        obj = _reuse_business_created_object(model, defaults)
    if obj is not None:
        return _apply_defaults_if_changed(obj, defaults)
    return model.objects.create(pk=pk, **defaults)


def choose(seq, index: int):
    return seq[index % len(seq)]


@dataclass
class SeedContext:
    as_of: datetime
    scale: str
    demo_password: str
    rng: random.Random = field(default_factory=lambda: random.Random(20260810))
    users: list[Any] = field(default_factory=list)
    staff_users: list[Any] = field(default_factory=list)
    organizations: list[Any] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)
    ticket_types: list[Any] = field(default_factory=list)
    orders: list[Any] = field(default_factory=list)
    tickets: list[Any] = field(default_factory=list)
    payments: list[Any] = field(default_factory=list)
    contacts: list[Any] = field(default_factory=list)
    crm_campaigns: list[Any] = field(default_factory=list)
    promotions: list[Any] = field(default_factory=list)
    affiliate_campaigns: list[Any] = field(default_factory=list)
    loyalty_programs: list[Any] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def cfg(self) -> dict[str, int]:
        return SCALE[self.scale]

    def add(self, label: str, amount: int = 1) -> None:
        self.stats[label] = self.stats.get(label, 0) + amount

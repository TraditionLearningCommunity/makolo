from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.apps import apps
from django.db import models

TZ = ZoneInfo("Africa/Lubumbashi")
NAMESPACE = uuid.UUID("5b6b4558-2b73-45c0-bdb4-b2a279b2560b")
SEED_TAG = "makolo-demo-2024-2027"
PROJECT_APPS = {
    "accounts", "organizations", "events", "tickets", "scanner", "payments",
    "notifications", "automation", "partners", "crm", "promotions", "loyalty",
    "analytics_app", "operations", "discovery", "growth",
}

SCALE = {
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


def upsert(model: type[models.Model], key: str, *, defaults: dict[str, Any]) -> models.Model:
    pk = stable_uuid(f"{model._meta.label_lower}:{key}")
    obj, _ = model.objects.update_or_create(pk=pk, defaults=defaults)
    return obj


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


def assert_model_coverage() -> list[str]:
    missing: list[str] = []
    covered: list[str] = []
    for model in apps.get_models():
        if model._meta.app_label not in PROJECT_APPS:
            continue
        if model._meta.proxy or model._meta.auto_created:
            continue
        count = model.objects.count()
        label = model._meta.label
        if count <= 0:
            missing.append(label)
        else:
            covered.append(f"{label}={count}")
    if missing:
        raise RuntimeError(
            "Le seed n'a pas couvert tous les modèles Makolo: " + ", ".join(sorted(missing))
        )
    return sorted(covered)

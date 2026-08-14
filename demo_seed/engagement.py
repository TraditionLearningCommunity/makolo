from __future__ import annotations

from .automation_demo import _seed_automation
from .canonical_crm_promotions import seed_canonical_crm_promotions
from .common import SeedContext
from .crm_demo import _seed_crm
from .notifications_growth import _seed_discovery_and_growth, _seed_notifications
from .promotions_demo import _seed_promotions


def seed_engagement(ctx: SeedContext) -> None:
    _seed_promotions(ctx)
    _seed_crm(ctx)
    seed_canonical_crm_promotions(ctx)
    _seed_notifications(ctx)
    _seed_discovery_and_growth(ctx)
    _seed_automation(ctx)
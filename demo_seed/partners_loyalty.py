from __future__ import annotations

from .analytics_demo import _seed_analytics_fact, _seed_growth_spend
from .common import SeedContext
from .loyalty_demo import _seed_loyalty
from .partners_demo import _seed_partners


def seed_partners_loyalty_and_analytics(ctx: SeedContext) -> None:
    _seed_partners(ctx)
    _seed_loyalty(ctx)
    _seed_growth_spend(ctx)
    _seed_analytics_fact(ctx)

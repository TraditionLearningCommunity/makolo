#!/usr/bin/env python
"""Deterministic Makolo demo/beta seed entry point."""
from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import transaction

from demo_seed.accounts_orgs import seed_accounts_and_organizations
from demo_seed.activities_demo import seed_activity_core
from demo_seed.authority import seed_contextual_authority
from demo_seed.beta import BETA_PERSONAS, seed_beta
from demo_seed.beta_validation import assert_beta_scenario_coverage
from demo_seed.common import SCALE, SeedContext
from demo_seed.engagement import seed_engagement
from demo_seed.events_commerce import seed_events_and_commerce
from demo_seed.operations import seed_operations_and_edge_cases
from demo_seed.partners_loyalty import seed_partners_loyalty_and_analytics
from demo_seed.transport import seed_transport

TZ = ZoneInfo("Africa/Lubumbashi")


@contextmanager
def _suspend_loyalty_seed_signals():
    """The seed builds deterministic snapshots and must not react to its own writes."""
    from django.db.models.signals import post_save
    from loyalty.signals import sync_checkin_points, sync_order_points
    from tickets.models import Ticket, TicketOrder

    bindings = [
        (sync_order_points, TicketOrder, "loyalty.sync_order_points"),
        (sync_checkin_points, Ticket, "loyalty.sync_checkin_points"),
    ]
    for _receiver, sender, dispatch_uid in bindings:
        post_save.disconnect(sender=sender, dispatch_uid=dispatch_uid)
    try:
        yield
    finally:
        for receiver, sender, dispatch_uid in bindings:
            post_save.connect(receiver, sender=sender, dispatch_uid=dispatch_uid)


def _parse_as_of(raw: str) -> datetime:
    if not raw:
        raise ValueError("--as-of est obligatoire (YYYY-MM-DD).")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--as-of doit utiliser le format YYYY-MM-DD.") from exc
    return parsed.replace(hour=12, tzinfo=TZ)


def run_seed(*, as_of: str, demo_password: str, scale: str = "beta") -> dict:
    if scale not in SCALE:
        raise ValueError(f"Profil de seed inconnu: {scale}")
    if not demo_password:
        raise ValueError("MAKOLO_DEMO_PASSWORD ou --demo-password est obligatoire.")

    ctx = SeedContext(as_of=_parse_as_of(as_of), scale=scale, demo_password=demo_password)
    validation = None
    with _suspend_loyalty_seed_signals(), transaction.atomic():
        if scale == "beta":
            seed_beta(ctx)
            validation = assert_beta_scenario_coverage(as_of=ctx.as_of)
        else:
            # Historical volume profiles remain useful for development load, but
            # they are not the canonical beta contract and no longer fabricate
            # arbitrary rows merely to cover every installed model.
            seed_accounts_and_organizations(ctx)
            seed_contextual_authority(ctx)
            seed_events_and_commerce(ctx)
            seed_activity_core(ctx)
            seed_engagement(ctx)
            seed_partners_loyalty_and_analytics(ctx)
            seed_operations_and_edge_cases(ctx)
            seed_transport(ctx)

    return {
        "scale": scale,
        "as_of": ctx.as_of.date().isoformat(),
        "stats": dict(sorted(ctx.stats.items())),
        "validation": validation or {},
        "login_examples": list(BETA_PERSONAS.values()) if scale == "beta" else [
            "demo.user001@makolo.test",
            "demo.user011@makolo.test",
            "demo.user026@makolo.test",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic Makolo demo data.")
    parser.add_argument("--scale", choices=sorted(SCALE), default="beta")
    parser.add_argument("--as-of", required=True, help="Reference date in Africa/Lubumbashi (YYYY-MM-DD).")
    parser.add_argument("--demo-password", default=os.environ.get("MAKOLO_DEMO_PASSWORD"))
    args = parser.parse_args()
    report = run_seed(scale=args.scale, as_of=args.as_of, demo_password=args.demo_password)
    print("Makolo demo seed complete")
    print(f"Scale: {report['scale']}")
    print(f"As of: {report['as_of']}")
    for label, amount in report["stats"].items():
        print(f"{label}: {amount}")
    if report["validation"]:
        print("Beta scenario validation:")
        for label, amount in report["validation"].items():
            print(f"  {label}: {amount}")
    print("Login examples:")
    for email in report["login_examples"]:
        print(f"  {email}")
    print("Password source: MAKOLO_DEMO_PASSWORD / --demo-password (value intentionally not printed).")


if __name__ == "__main__":
    main()

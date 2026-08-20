from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Lubumbashi")


def _parse_as_of(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--as-of doit être au format YYYY-MM-DD.") from exc
    return parsed.replace(hour=12, minute=0, tzinfo=TZ)


@contextmanager
def _suspend_loyalty_seed_signals():
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


def run_seed(*, scale: str = "large", as_of: str = "2026-08-10", demo_password: str) -> dict:
    from django.db import transaction
    from demo_seed.accounts_orgs import seed_accounts_and_organizations
    from demo_seed.activities_demo import seed_activity_core
    from demo_seed.authority import seed_contextual_authority
    from demo_seed.common import SeedContext, assert_model_coverage
    from demo_seed.engagement import seed_engagement
    from demo_seed.events_commerce import seed_events_and_commerce
    from demo_seed.operations import seed_operations_and_edge_cases
    from demo_seed.partners_loyalty import seed_partners_loyalty_and_analytics
    from demo_seed.transport import seed_transport

    ctx = SeedContext(as_of=_parse_as_of(as_of), scale=scale, demo_password=demo_password)
    with _suspend_loyalty_seed_signals(), transaction.atomic():
        seed_accounts_and_organizations(ctx)
        seed_contextual_authority(ctx)
        seed_events_and_commerce(ctx)
        seed_activity_core(ctx)
        seed_engagement(ctx)
        seed_partners_loyalty_and_analytics(ctx)
        seed_operations_and_edge_cases(ctx)
        # Transport is seeded last on purpose: no Event seed step can attach an
        # artificial Event to the Mulykap Transport Activity.
        seed_transport(ctx)
        coverage = assert_model_coverage()
    return {
        "as_of": ctx.as_of.isoformat(),
        "scale": scale,
        "stats": dict(sorted(ctx.stats.items())),
        "coverage": coverage,
        "login_examples": ["demo.user001@makolo.test", "demo.user002@makolo.test", "demo.user011@makolo.test", "demo.user026@makolo.test"],
    }


def _bootstrap_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Peuple Makolo avec un historique réaliste 2024-2027. La génération est déterministe et peut être relancée.")
    parser.add_argument("--scale", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--as-of", default="2026-08-10")
    parser.add_argument("--demo-password", default=os.environ.get("MAKOLO_DEMO_PASSWORD", ""), help="Mot de passe appliqué aux comptes demo.*. Peut aussi venir de MAKOLO_DEMO_PASSWORD.")
    args = parser.parse_args()
    if not args.demo_password:
        parser.error("Fournissez --demo-password ou la variable MAKOLO_DEMO_PASSWORD. Aucun mot de passe de démonstration n'est stocké dans Git.")
    _bootstrap_django()
    result = run_seed(scale=args.scale, as_of=args.as_of, demo_password=args.demo_password)
    print("\n=== MAKOLO DEMO DATA READY ===")
    print(f"Référence temporelle : {result['as_of']}")
    print(f"Échelle : {result['scale']}")
    for key, value in result["stats"].items(): print(f"- {key}: {value}")
    print(f"- modèles métier couverts: {len(result['coverage'])}")
    print("Comptes de connexion exemples :")
    for email in result["login_examples"]: print(f"  - {email}")
    print("Tous utilisent le mot de passe fourni à la commande.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

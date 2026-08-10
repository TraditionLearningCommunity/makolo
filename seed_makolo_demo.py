from __future__ import annotations

import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Lubumbashi")


def _parse_as_of(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--as-of doit être au format YYYY-MM-DD.") from exc
    return parsed.replace(hour=12, minute=0, tzinfo=TZ)


def run_seed(*, scale: str = "large", as_of: str = "2026-08-10", demo_password: str) -> dict:
    from django.db import transaction

    from demo_seed.accounts_orgs import seed_accounts_and_organizations
    from demo_seed.common import SeedContext, assert_model_coverage
    from demo_seed.engagement import seed_engagement
    from demo_seed.events_commerce import seed_events_and_commerce
    from demo_seed.operations import seed_operations_and_edge_cases
    from demo_seed.partners_loyalty import seed_partners_loyalty_and_analytics

    ctx = SeedContext(
        as_of=_parse_as_of(as_of),
        scale=scale,
        demo_password=demo_password,
    )

    with transaction.atomic():
        seed_accounts_and_organizations(ctx)
        seed_events_and_commerce(ctx)
        seed_engagement(ctx)
        seed_partners_loyalty_and_analytics(ctx)
        seed_operations_and_edge_cases(ctx)
        coverage = assert_model_coverage()

    return {
        "as_of": ctx.as_of.isoformat(),
        "scale": scale,
        "stats": dict(sorted(ctx.stats.items())),
        "coverage": coverage,
        "login_examples": [
            "demo.user001@makolo.test",
            "demo.user002@makolo.test",
            "demo.user011@makolo.test",
            "demo.user026@makolo.test",
        ],
    }


def _bootstrap_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Peuple Makolo avec un historique réaliste 2024-2027. "
            "La génération est déterministe et peut être relancée."
        )
    )
    parser.add_argument("--scale", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--as-of", default="2026-08-10")
    parser.add_argument(
        "--demo-password",
        default=os.environ.get("MAKOLO_DEMO_PASSWORD", ""),
        help="Mot de passe appliqué aux comptes demo.*. Peut aussi venir de MAKOLO_DEMO_PASSWORD.",
    )
    args = parser.parse_args()
    if not args.demo_password:
        parser.error(
            "Fournissez --demo-password ou la variable MAKOLO_DEMO_PASSWORD. "
            "Aucun mot de passe de démonstration n'est stocké dans Git."
        )

    _bootstrap_django()
    result = run_seed(scale=args.scale, as_of=args.as_of, demo_password=args.demo_password)

    print("\n=== MAKOLO DEMO DATA READY ===")
    print(f"Référence temporelle : {result['as_of']}")
    print(f"Échelle : {result['scale']}")
    for key, value in result["stats"].items():
        print(f"- {key}: {value}")
    print(f"- modèles métier couverts: {len(result['coverage'])}")
    print("Comptes de connexion exemples :")
    for email in result["login_examples"]:
        print(f"  - {email}")
    print("Tous utilisent le mot de passe fourni à la commande.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

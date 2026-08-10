from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from seed_makolo_demo import run_seed


class Command(BaseCommand):
    help = (
        "Peuple Makolo avec des données de démonstration réalistes et déterministes "
        "de 2024 à 2027, couvrant tous les modèles métier."
    )

    def add_arguments(self, parser):
        parser.add_argument("--scale", choices=["small", "medium", "large"], default="large")
        parser.add_argument("--as-of", default="2026-08-10")
        parser.add_argument(
            "--demo-password",
            default=os.environ.get("MAKOLO_DEMO_PASSWORD", ""),
            help="Mot de passe appliqué aux comptes demo.* ; peut venir de MAKOLO_DEMO_PASSWORD.",
        )

    def handle(self, *args, **options):
        password = options["demo_password"]
        if not password:
            raise CommandError(
                "Fournissez --demo-password ou MAKOLO_DEMO_PASSWORD. "
                "Aucun mot de passe de démonstration n'est stocké dans le dépôt."
            )
        try:
            result = run_seed(
                scale=options["scale"],
                as_of=options["as_of"],
                demo_password=password,
            )
        except Exception as exc:
            raise CommandError(f"Le seeding Makolo a échoué : {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Makolo demo data générées avec succès."))
        self.stdout.write(f"Référence : {result['as_of']} | échelle : {result['scale']}")
        for key, value in result["stats"].items():
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write(f"  modèles métier couverts: {len(result['coverage'])}")
        self.stdout.write("Comptes de connexion exemples :")
        for email in result["login_examples"]:
            self.stdout.write(f"  - {email}")
        self.stdout.write("Tous utilisent le mot de passe fourni à la commande.")

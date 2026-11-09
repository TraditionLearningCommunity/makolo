"""Populate Projects/Dossiers for an *existing* Mobile Mature synthetic persona.

This targeted command never creates users, rewrites credentials, or runs on
unknown real profiles. It does not deploy or schedule itself.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from demo_seed.common import SeedContext, stable_uuid
from demo_seed.mobile_mature_universe import (
    MOBILE_MATURE_PERSONAS, SEED_MARKER,
)
from demo_seed.mobile_objectives import seed_mobile_objectives
from demo_seed.mobile_mature_validation import assert_mobile_mature_demo_coverage


class Command(BaseCommand):
    help = "Add idempotent canonical Projects/Dossiers to an existing Mobile Mature demo database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of", required=True,
            help="Reference date YYYY-MM-DD in Africa/Lubumbashi.",
        )
        parser.add_argument(
            "--confirm-demo-database",
            action="store_true",
            help="Confirm this is an isolated demo/test database, never production.",
        )

    def handle(self, *args, **options):
        if not options["confirm_demo_database"]:
            raise CommandError(
                "Confirm an isolated test database with --confirm-demo-database."
            )
        try:
            as_of = datetime.strptime(options["as_of"], "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0,
                tzinfo=ZoneInfo("Africa/Lubumbashi"),
            )
        except ValueError as exc:
            raise CommandError("--as-of doit utiliser YYYY-MM-DD.") from exc

        primary = User.objects.filter(
            pk=stable_uuid("accounts.user:mobile-mature-primary"),
            email=MOBILE_MATURE_PERSONAS["primary"],
        ).first()
        if (
            primary is None
            or not isinstance(primary.metadata, dict)
            or primary.metadata.get("seed") != SEED_MARKER
            or primary.metadata.get("persona") != "primary"
        ):
            raise CommandError(
                "Persona Mobile Mature synthétique introuvable. "
                "Exécutez d'abord seed_mobile_mature_demo sur une base de test."
            )

        ctx = SeedContext(as_of=as_of, scale="beta", demo_password="")
        try:
            with transaction.atomic():
                seed_mobile_objectives(ctx, primary=primary)
                counts = assert_mobile_mature_demo_coverage()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Mobile Objectives demo: OK"))
        for label in (
            "mobile_mature_projects", "mobile_mature_dossiers",
            "mobile_mature_project_dossier_links",
            "mobile_mature_dossier_journey_links",
            "mobile_mature_dossier_dependencies",
            "mobile_mature_organizer_visible_items",
        ):
            self.stdout.write(f"{label}: {counts[label]}")
        self.stdout.write("Aucun mot de passe ni donnée de compte réel modifiés.")

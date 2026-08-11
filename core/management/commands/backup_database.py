import os
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Crée une sauvegarde SQLite cohérente avec l'API backup de SQLite, "
        "puis vérifie son intégrité."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(settings.MAKOLO_BACKUP_DIR),
            help="Répertoire de destination (défaut: MAKOLO_BACKUP_DIR).",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError(
                "backup_database est réservé à SQLite. Utilisez l'outil natif "
                "du moteur configuré pour une autre base."
            )

        output_dir = Path(options["output_dir"]).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
        destination = output_dir / f"makolo-{timestamp}.sqlite3"
        temporary = destination.with_suffix(".sqlite3.tmp")
        if destination.exists() or temporary.exists():
            raise CommandError(
                f"Une sauvegarde existe déjà pour cet horodatage: {destination}"
            )

        connection.ensure_connection()
        source = connection.connection
        destination_connection = None
        try:
            destination_connection = sqlite3.connect(temporary)
            source.backup(destination_connection)
            result = destination_connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise CommandError(
                    f"Vérification SQLite en échec pour {temporary}: {result!r}"
                )
            destination_connection.close()
            destination_connection = None
            os.replace(temporary, destination)
        except Exception:
            if destination_connection is not None:
                destination_connection.close()
            temporary.unlink(missing_ok=True)
            raise

        if not destination.exists() or destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
            raise CommandError("La sauvegarde créée est vide ou introuvable.")

        self.stdout.write(self.style.SUCCESS(str(destination)))

from django.core.management.base import BaseCommand, CommandError

from projector.services import build_full_snapshot


class Command(BaseCommand):
    help = (
        "Construit déterministement le snapshot Actor 7. "
        "L'application à Actor 8 reste indisponible tant que son runtime n'existe pas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Construit et valide le snapshot sans l'envoyer à Actor 8.",
        )

    def handle(self, *args, **options):
        if not options["dry_run"]:
            raise CommandError(
                "Actor 8 n'est pas encore connecté. Utilisez --dry-run pour valider "
                "la reconstruction sans inventer de provider."
            )
        snapshot = build_full_snapshot()
        self.stdout.write(
            self.style.SUCCESS(
                " ".join(
                    (
                        f"scope={snapshot.scope_ref}",
                        f"strategy={snapshot.strategy_version}",
                        f"roots={len(snapshot.roots)}",
                        f"fingerprint={snapshot.semantic_fingerprint}",
                    )
                )
            )
        )

from django.core.management.base import BaseCommand

from domain_events.services import process_domain_events, recover_stale_domain_events


class Command(BaseCommand):
    help = "Traite la transactional outbox des Domain Events Makolo."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--once",
            action="store_true",
            help="Traite au maximum un batch puis s'arrête.",
        )
        parser.add_argument(
            "--recover-stale-minutes",
            type=int,
            default=15,
            help="Remet en attente les claims interrompus plus anciens que ce délai.",
        )

    def handle(self, *args, **options):
        batch_size = max(options["batch_size"], 1)
        limit = options["limit"]
        if options["once"]:
            limit = batch_size if limit is None else min(limit, batch_size)
        recovered = recover_stale_domain_events(
            stale_minutes=max(options["recover_stale_minutes"], 1)
        )
        stats = process_domain_events(batch_size=batch_size, limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                "Domain Events: "
                f"recovered={recovered} claimed={stats['claimed']} "
                f"processed={stats['processed']} retry={stats['retry']} failed={stats['failed']}"
            )
        )

from django.core.management.base import BaseCommand

from notifications.services import dispatch_pending


class Command(BaseCommand):
    help = "Envoie les livraisons de notifications arrivées à échéance."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        result = dispatch_pending(limit=max(options["limit"], 1))
        self.stdout.write(
            self.style.SUCCESS(
                "Notifications traitées — "
                + ", ".join(f"{key}: {value}" for key, value in result.items())
            )
        )

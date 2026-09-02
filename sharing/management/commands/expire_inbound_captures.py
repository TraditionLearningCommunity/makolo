from django.core.management.base import BaseCommand

from sharing.document_services import expire_captures


class Command(BaseCommand):
    help = "Expire et nettoie les InboundCapture privées arrivées à échéance."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        count = expire_captures(limit=max(1, options["limit"]))
        self.stdout.write(self.style.SUCCESS(f"{count} capture(s) expirée(s)."))

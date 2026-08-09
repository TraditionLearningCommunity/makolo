import json

from django.core.management.base import BaseCommand

from crm.services import process_due_campaigns


class Command(BaseCommand):
    help = "Traite les campagnes CRM planifiées et leur file de destinataires."

    def add_arguments(self, parser):
        parser.add_argument("--campaign-limit", type=int, default=20)
        parser.add_argument("--recipient-limit", type=int, default=100)

    def handle(self, *args, **options):
        result = process_due_campaigns(
            campaign_limit=max(options["campaign_limit"], 1),
            recipient_limit=max(options["recipient_limit"], 1),
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, default=str))

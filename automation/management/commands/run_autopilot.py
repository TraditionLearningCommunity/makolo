import json

from django.core.management.base import BaseCommand

from automation.services import run_autopilot_cycle


class Command(BaseCommand):
    help = "Exécute un cycle Makolo Autopilot (scheduler, expirations, notifications)."

    def add_arguments(self, parser):
        parser.add_argument("--delivery-limit", type=int, default=100)

    def handle(self, *args, **options):
        stats = run_autopilot_cycle(delivery_limit=max(options["delivery_limit"], 1))
        self.stdout.write(self.style.SUCCESS(json.dumps(stats, ensure_ascii=False, default=str)))

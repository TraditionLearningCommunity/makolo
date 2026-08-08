from django.core.management.base import BaseCommand, CommandError

from notifications.services import schedule_event_reminders


class Command(BaseCommand):
    help = "Crée les rappels d’événements pour les détenteurs de billets valides."

    def add_arguments(self, parser):
        parser.add_argument("--hours-before", type=int, default=24)
        parser.add_argument("--window-minutes", type=int, default=60)

    def handle(self, *args, **options):
        hours_before = options["hours_before"]
        window_minutes = options["window_minutes"]
        if hours_before < 0 or window_minutes < 1:
            raise CommandError("Les paramètres de rappel doivent être positifs.")
        created = schedule_event_reminders(
            hours_before=hours_before,
            window_minutes=window_minutes,
        )
        self.stdout.write(self.style.SUCCESS(f"{created} rappel(s) créé(s)."))

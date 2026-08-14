from django.core.management.base import BaseCommand

from capacity.services import expire_stale_capacity_reservations


class Command(BaseCommand):
    help = "Expire les holds Capacity arrivés à échéance."

    def handle(self, *args, **options):
        count = expire_stale_capacity_reservations()
        self.stdout.write(self.style.SUCCESS(f"{count} hold(s) Capacity expiré(s)."))

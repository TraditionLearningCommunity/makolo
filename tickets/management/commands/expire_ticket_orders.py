from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import TicketOrder, TicketOrderStatus
from tickets.services import expire_order


class Command(BaseCommand):
    help = "Libère le stock des commandes de billets expirées."

    def handle(self, *args, **options):
        queryset = TicketOrder.objects.filter(
            status=TicketOrderStatus.PENDING,
            expires_at__isnull=False,
            expires_at__lte=timezone.now(),
        ).order_by("expires_at")

        expired = 0
        for order in queryset.iterator():
            expire_order(order=order)
            expired += 1

        self.stdout.write(
            self.style.SUCCESS(f"{expired} commande(s) expirée(s) traitée(s).")
        )

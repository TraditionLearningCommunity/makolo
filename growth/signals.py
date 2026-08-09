from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder

from .services import sync_marketing_attribution


@receiver(post_save, sender=TicketOrder)
def sync_marketing_attribution_on_order_save(sender, instance, **kwargs):
    if hasattr(instance, "marketing_attribution"):
        sync_marketing_attribution(instance)

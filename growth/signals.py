from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder

from .services import attribute_order_from_recent_user_visit, sync_marketing_attribution


@receiver(post_save, sender=TicketOrder)
def sync_marketing_attribution_on_order_save(sender, instance, **kwargs):
    attribution = sync_marketing_attribution(instance)
    if attribution is None and instance.buyer_id:
        attribute_order_from_recent_user_visit(instance)

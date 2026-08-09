from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder

from .models import MarketingAttributionStatus
from .services import attribute_order_from_recent_user_visit, sync_marketing_attribution


@receiver(post_save, sender=TicketOrder)
def sync_marketing_attribution_on_order_save(sender, instance, **kwargs):
    attribution = sync_marketing_attribution(instance)
    if attribution is None and instance.buyer_id:
        attribution = attribute_order_from_recent_user_visit(instance)
    if attribution is None:
        return

    # Promotions may legitimately change a pending order total before payment.
    # Keep the attribution snapshot aligned until confirmation. Once confirmed,
    # the order amount itself is immutable through normal checkout flows.
    desired_amount = instance.total_amount
    desired_currency = (instance.currency or "").upper()
    changed = []
    if attribution.revenue_amount != desired_amount:
        attribution.revenue_amount = desired_amount
        changed.append("revenue_amount")
    if attribution.currency != desired_currency:
        attribution.currency = desired_currency
        changed.append("currency")
    if changed:
        attribution.save(update_fields=changed)

from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder, TicketOrderStatus

from .canonical_models import CommercePromotionRedemption
from .models import PromotionRedemption
from .services import confirm_redemption, reverse_redemption


def _project_commerce_redemption(redemption, *, order=None):
    """Keep the historical TicketOrder relation as a readonly projection."""
    if order is None:
        order = TicketOrder.objects.filter(commerce_order_id=redemption.commerce_order_id).first()
    if order is None:
        return None
    projected, _created = PromotionRedemption.objects.update_or_create(
        order=order,
        defaults={
            "promotion": redemption.promotion,
            "code": redemption.code,
            "buyer": redemption.buyer,
            "customer_email": redemption.customer_email,
            "status": redemption.status,
            "subtotal_amount": redemption.subtotal_amount,
            "eligible_amount": redemption.eligible_amount,
            "discount_amount": redemption.discount_amount,
            "final_amount": redemption.final_amount,
            "currency": redemption.currency,
            "confirmed_at": redemption.confirmed_at,
            "reversed_at": redemption.reversed_at,
        },
    )
    return projected


@receiver(post_save, sender=CommercePromotionRedemption, dispatch_uid="promotions.project_commerce_redemption")
def project_commerce_redemption(sender, instance, **kwargs):
    _project_commerce_redemption(instance)


@receiver(post_save, sender=TicketOrder, dispatch_uid="promotions.sync_order_redemption")
def sync_order_redemption(sender, instance, **kwargs):
    if instance.commerce_order_id:
        canonical = CommercePromotionRedemption.objects.filter(
            commerce_order_id=instance.commerce_order_id
        ).first()
        if canonical is not None:
            _project_commerce_redemption(canonical, order=instance)

    if instance.status == TicketOrderStatus.CONFIRMED:
        confirm_redemption(order=instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_redemption(order=instance)

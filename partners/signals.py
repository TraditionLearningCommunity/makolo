from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from tickets.models import TicketOrder, TicketOrderStatus

from .models import AttributionStatus, PartnerPayout, ReferralAttribution
from .services import confirm_order_attribution, reverse_order_attribution


@receiver(pre_save, sender=ReferralAttribution, dispatch_uid="partners.prevent_self_referral")
def prevent_self_referral(sender, instance, **kwargs):
    """Keep an audit record of self-referral but never make it commissionable."""
    if not instance.order_id or not instance.partner_id:
        return
    buyer_id = instance.order.buyer_id
    partner_user_id = instance.partner.user_id
    if buyer_id and partner_user_id and buyer_id == partner_user_id:
        instance.status = AttributionStatus.REVERSED
        instance.reversed_at = instance.reversed_at or timezone.now()


@receiver(pre_save, sender=PartnerPayout, dispatch_uid="partners.prevent_zero_payout")
def prevent_zero_payout(sender, instance, **kwargs):
    if instance.amount is not None and instance.amount <= 0:
        raise ValidationError("Un paiement partenaire doit avoir un montant strictement positif.")


@receiver(post_save, sender=TicketOrder, dispatch_uid="partners.sync_order_attribution")
def sync_order_attribution(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        confirm_order_attribution(order=instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_order_attribution(order=instance)

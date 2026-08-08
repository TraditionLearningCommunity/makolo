from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from payments.models import Payment, PaymentStatus
from tickets.models import TicketOrder, TicketOrderStatus

from .services import (
    notify_order_confirmed,
    notify_payment_failed,
    notify_payment_refunded,
    notify_payment_succeeded,
)


@receiver(post_save, sender=TicketOrder)
def queue_free_order_notification(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED and instance.total_amount == 0:
        transaction.on_commit(lambda pk=instance.pk: notify_order_confirmed(pk))


@receiver(post_save, sender=Payment)
def queue_payment_notification(sender, instance, **kwargs):
    callbacks = {
        PaymentStatus.SUCCEEDED: notify_payment_succeeded,
        PaymentStatus.FAILED: notify_payment_failed,
        PaymentStatus.REFUNDED: notify_payment_refunded,
    }
    callback = callbacks.get(instance.status)
    if callback:
        transaction.on_commit(lambda pk=instance.pk, fn=callback: fn(pk))

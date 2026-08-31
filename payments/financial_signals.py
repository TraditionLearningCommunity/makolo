from django.db.models.signals import post_save
from django.dispatch import receiver

from .financial_services import (
    recognize_evidence_financials,
    recognize_payment_financials,
    record_refund_financials,
)
from .models import (
    Payment,
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentStatus,
    Refund,
    RefundStatus,
)


@receiver(post_save, sender=Payment, dispatch_uid="payments.f3.payment_recognition")
def recognize_succeeded_payment(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == PaymentStatus.SUCCEEDED:
        recognize_payment_financials(payment=instance)


@receiver(post_save, sender=PaymentEvidence, dispatch_uid="payments.f3.evidence_recognition")
def recognize_verified_evidence(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == PaymentEvidenceStatus.VERIFIED:
        recognize_evidence_financials(evidence=instance)


@receiver(post_save, sender=Refund, dispatch_uid="payments.f3.refund_recognition")
def recognize_succeeded_refund(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == RefundStatus.SUCCEEDED:
        record_refund_financials(refund=instance)

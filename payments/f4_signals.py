from django.db.models.signals import post_save
from django.dispatch import receiver

from .f4_services import recognize_obligation_fund_flow
from .models import Payment, PaymentEvidence, PaymentEvidenceStatus, PaymentStatus


@receiver(post_save, sender=Payment, dispatch_uid="payments.f4.payment_fund_flow")
def recognize_payment_fund_flow(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == PaymentStatus.SUCCEEDED and instance.obligation_id:
        recognize_obligation_fund_flow(obligation=instance.obligation)


@receiver(post_save, sender=PaymentEvidence, dispatch_uid="payments.f4.evidence_fund_flow")
def recognize_evidence_fund_flow(sender, instance, raw=False, **kwargs):
    if not raw and instance.status == PaymentEvidenceStatus.VERIFIED:
        recognize_obligation_fund_flow(obligation=instance.obligation)

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import CommissionStatus, PartnerCommission, PartnerPayout, PayoutStatus, ReferralCode


def _queue_notification(callback):
    transaction.on_commit(callback)


@receiver(post_save, sender=ReferralCode, dispatch_uid="partners.notify_referral_code")
def notify_referral_code(sender, instance, created, **kwargs):
    if not created or not instance.partner.user_id:
        return
    partner = instance.partner
    campaign = instance.campaign

    def send():
        create_notification(
            recipient=partner.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Votre lien ambassadeur est prêt",
            message=(
                f"{campaign.organization.name} vous a attribué le code {instance.code} "
                f"pour « {campaign.event.title} ». Vos conversions seront visibles dans votre espace partenaire."
            ),
            action_url=reverse("partners:partner-detail", kwargs={"pk": partner.pk}),
            dedup_key=f"partner-code-created:{instance.pk}",
            metadata={"partner_id": str(partner.pk), "campaign_id": str(campaign.pk), "code_id": str(instance.pk)},
        )

    _queue_notification(send)


@receiver(post_save, sender=PartnerCommission, dispatch_uid="partners.notify_commission_earned")
def notify_commission_earned(sender, instance, created, **kwargs):
    if not created or instance.status != CommissionStatus.EARNED or not instance.partner.user_id:
        return
    partner = instance.partner

    def send():
        create_notification(
            recipient=partner.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.PAYMENT,
            title="Nouvelle commission acquise",
            message=(
                f"Une conversion confirmée pour « {instance.campaign.event.title} » "
                f"a généré {instance.amount} {instance.currency} de commission."
            ),
            action_url=reverse("partners:partner-detail", kwargs={"pk": partner.pk}),
            dedup_key=f"partner-commission-earned:{instance.pk}",
            metadata={"partner_id": str(partner.pk), "commission_id": str(instance.pk)},
        )

    _queue_notification(send)


@receiver(post_save, sender=PartnerPayout, dispatch_uid="partners.notify_payout_paid")
def notify_payout_paid(sender, instance, **kwargs):
    if instance.status != PayoutStatus.PAID or not instance.partner.user_id:
        return
    partner = instance.partner

    def send():
        create_notification(
            recipient=partner.user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.PAYMENT,
            title="Commission marquée comme payée",
            message=(
                f"{instance.organization.name} a marqué un règlement de {instance.amount} {instance.currency} comme payé. "
                f"Référence : {instance.reference or 'non renseignée'}."
            ),
            action_url=reverse("partners:partner-detail", kwargs={"pk": partner.pk}),
            dedup_key=f"partner-payout-paid:{instance.pk}",
            metadata={"partner_id": str(partner.pk), "payout_id": str(instance.pk)},
        )

    _queue_notification(send)

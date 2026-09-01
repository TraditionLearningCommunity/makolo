from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import Dispute, DisputeStatus, Proof, ProofStatus, Report, VerificationClaim, VerificationStatus


def _remember_status(instance, model):
    if not instance.pk:
        instance._trust_previous_status = None
        return
    instance._trust_previous_status = model.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


def _notify(recipient, *, title, message, dedup_key, journey=None):
    if recipient is None:
        return
    create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title=title,
        message=message,
        dedup_key=dedup_key,
        queue_email=False,
        journey=journey,
    )


def _unique_recipients(*profiles):
    seen = set()
    for profile in profiles:
        if profile is None or profile.pk in seen:
            continue
        seen.add(profile.pk)
        yield profile


@receiver(pre_save, sender=VerificationClaim, dispatch_uid="trust.capture_verification_status")
def capture_verification_status(sender, instance, **kwargs):
    _remember_status(instance, VerificationClaim)


@receiver(post_save, sender=VerificationClaim, dispatch_uid="trust.notify_verification_status")
def notify_verification_status(sender, instance, created, **kwargs):
    previous = getattr(instance, "_trust_previous_status", None)
    if created and instance.status == VerificationStatus.REQUESTED:
        _notify(
            instance.requested_by,
            title="Demande de vérification reçue",
            message="Makolo a enregistré votre demande de vérification.",
            dedup_key=f"trust:verification:{instance.pk}:requested",
        )
        return
    if previous == instance.status:
        return
    copy = {
        VerificationStatus.VERIFIED: ("Vérification confirmée", "Makolo a confirmé le claim de vérification concerné."),
        VerificationStatus.REJECTED: ("Vérification non confirmée", "Makolo a terminé la review sans confirmer ce claim."),
        VerificationStatus.REVOKED: ("Vérification révoquée", "Makolo a révoqué un claim précédemment vérifié."),
    }.get(instance.status)
    if not copy:
        return
    for recipient in _unique_recipients(instance.requested_by, instance.subject_profile):
        _notify(
            recipient,
            title=copy[0],
            message=copy[1],
            dedup_key=f"trust:verification:{instance.pk}:{instance.status}:{recipient.pk}",
        )


@receiver(post_save, sender=Report, dispatch_uid="trust.notify_report_created")
def notify_report_created(sender, instance, created, **kwargs):
    if not created:
        return
    _notify(
        instance.reporter,
        title="Signalement reçu",
        message="Makolo a enregistré votre signalement et pourra l’examiner.",
        dedup_key=f"trust:report:{instance.pk}:created",
        journey=instance.journey,
    )


@receiver(pre_save, sender=Dispute, dispatch_uid="trust.capture_dispute_status")
def capture_dispute_status(sender, instance, **kwargs):
    _remember_status(instance, Dispute)


@receiver(post_save, sender=Dispute, dispatch_uid="trust.notify_dispute_status")
def notify_dispute_status(sender, instance, created, **kwargs):
    previous = getattr(instance, "_trust_previous_status", None)
    if created:
        status_key = DisputeStatus.OPEN
        title = "Dossier de résolution ouvert"
        message = "Makolo a ouvert un dossier de résolution lié à votre expérience."
    elif previous != instance.status and instance.status == DisputeStatus.AWAITING_INFORMATION:
        status_key = instance.status
        title = "Information demandée"
        message = "Le dossier Makolo attend une information complémentaire."
    elif previous != instance.status and instance.status == DisputeStatus.DECIDED:
        status_key = instance.status
        title = "Décision de dossier disponible"
        message = "Makolo a enregistré une décision sur le dossier de résolution."
    elif previous != instance.status and instance.status == DisputeStatus.CLOSED:
        status_key = instance.status
        title = "Dossier de résolution clos"
        message = "Le dossier de résolution Makolo est clos."
    else:
        return
    for recipient in _unique_recipients(instance.claimant, instance.respondent_profile):
        _notify(
            recipient,
            title=title,
            message=message,
            dedup_key=f"trust:dispute:{instance.pk}:{status_key}:{recipient.pk}",
            journey=instance.journey,
        )


@receiver(pre_save, sender=Proof, dispatch_uid="trust.capture_proof_status")
def capture_proof_status(sender, instance, **kwargs):
    _remember_status(instance, Proof)


@receiver(post_save, sender=Proof, dispatch_uid="trust.notify_proof_status")
def notify_proof_status(sender, instance, created, **kwargs):
    previous = getattr(instance, "_trust_previous_status", None)
    if created:
        title = "Attestation disponible"
        message = "Makolo a émis une attestation à partir d’un fait canonique établi."
        status_key = "issued"
    elif previous != instance.status and instance.status == ProofStatus.REVOKED:
        title = "Attestation révoquée"
        message = "Makolo a révoqué une attestation ; son historique reste conservé."
        status_key = "revoked"
    else:
        return
    _notify(
        instance.subject_profile,
        title=title,
        message=message,
        dedup_key=f"trust:proof:{instance.pk}:{status_key}",
        journey=instance.journey,
    )

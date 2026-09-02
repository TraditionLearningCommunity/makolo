from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import Occurrence
from activities.selectors import publicly_visible_activities
from discovery.search import get_public_occurrence
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from opportunities.selectors import published_opportunities

from .models import (
    ActivityShareSubject,
    OpportunityShareSubject,
    ShareDelivery,
    ShareEnvelope,
    ShareIntent,
    ShareLink,
    ShareStatus,
    ShareSubjectType,
)


ACTIVITY_INTENTS = {ShareIntent.VIEW, ShareIntent.PARTICIPATE}
OPPORTUNITY_INTENTS = {ShareIntent.VIEW, ShareIntent.START_JOURNEY}
TOKEN_BYTES = 32


class ShareUnavailable(Exception):
    pass


@dataclass(frozen=True)
class CreatedShare:
    envelope: ShareEnvelope
    raw_token: str


@dataclass(frozen=True)
class CreatedDirectShare:
    envelope: ShareEnvelope
    delivery: ShareDelivery


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def share_public_url(raw_token: str) -> str:
    return f"{settings.MAKOLO_PUBLIC_BASE_URL}{reverse('sharing:landing', kwargs={'token': raw_token})}"


def share_qr_url(raw_token: str) -> str:
    return f"{settings.MAKOLO_PUBLIC_BASE_URL}{reverse('sharing:qr', kwargs={'token': raw_token})}"


def _validate_expiry(expires_at):
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError({"expires_at": "L’expiration doit être future."})


def _create_envelope(*, created_by, subject_type, intent, expires_at=None):
    _validate_expiry(expires_at)
    return ShareEnvelope.objects.create(
        created_by=created_by,
        subject_type=subject_type,
        intent=intent,
        expires_at=expires_at,
    )


def _attach_link(envelope):
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    ShareLink.objects.create(envelope=envelope, token_hash=token_digest(raw_token))
    return raw_token


def _validate_activity(*, activity, occurrence, intent):
    if intent not in ACTIVITY_INTENTS:
        raise ValidationError({"intent": "Cette intention n’est pas supportée pour une Activity."})
    if intent == ShareIntent.PARTICIPATE and occurrence is None:
        raise ValidationError({"intent": "Participer exige une Occurrence précise."})
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L’Occurrence doit appartenir à l’Activity partagée."})
    if not publicly_visible_activities().filter(pk=activity.pk).exists():
        raise ValidationError("Cette Activity n’est pas partageable.")
    if occurrence is not None:
        try:
            public_occurrence = get_public_occurrence(occurrence.pk)
        except Occurrence.DoesNotExist as exc:
            raise ValidationError("Cette Occurrence n’est pas partageable.") from exc
        if public_occurrence.activity_id != activity.pk:
            raise ValidationError({"occurrence": "Le contexte Activity/Occurrence est incohérent."})
        occurrence = public_occurrence
    return occurrence


def _create_activity_envelope(*, created_by, activity, occurrence=None, intent=ShareIntent.VIEW, expires_at=None):
    occurrence = _validate_activity(activity=activity, occurrence=occurrence, intent=intent)
    envelope = _create_envelope(
        created_by=created_by,
        subject_type=ShareSubjectType.ACTIVITY,
        intent=intent,
        expires_at=expires_at,
    )
    ActivityShareSubject.objects.create(envelope=envelope, activity=activity, occurrence=occurrence)
    return envelope


def _validate_opportunity(*, opportunity_revision, intent):
    if intent not in OPPORTUNITY_INTENTS:
        raise ValidationError({"intent": "Cette intention n’est pas supportée pour une Opportunity."})
    opportunity = published_opportunities().filter(pk=opportunity_revision.opportunity_id).first()
    if opportunity is None or opportunity.current_revision_id != opportunity_revision.pk:
        raise ValidationError("Seule la révision publiée courante peut être partagée.")


def _create_opportunity_envelope(*, created_by, opportunity_revision, intent=ShareIntent.VIEW, expires_at=None):
    _validate_opportunity(opportunity_revision=opportunity_revision, intent=intent)
    envelope = _create_envelope(
        created_by=created_by,
        subject_type=ShareSubjectType.OPPORTUNITY,
        intent=intent,
        expires_at=expires_at,
    )
    OpportunityShareSubject.objects.create(
        envelope=envelope,
        opportunity_revision=opportunity_revision,
    )
    return envelope


@transaction.atomic
def create_activity_share(*, created_by, activity, occurrence=None, intent=ShareIntent.VIEW, expires_at=None):
    envelope = _create_activity_envelope(
        created_by=created_by,
        activity=activity,
        occurrence=occurrence,
        intent=intent,
        expires_at=expires_at,
    )
    return CreatedShare(envelope=envelope, raw_token=_attach_link(envelope))


@transaction.atomic
def create_opportunity_share(*, created_by, opportunity_revision, intent=ShareIntent.VIEW, expires_at=None):
    envelope = _create_opportunity_envelope(
        created_by=created_by,
        opportunity_revision=opportunity_revision,
        intent=intent,
        expires_at=expires_at,
    )
    return CreatedShare(envelope=envelope, raw_token=_attach_link(envelope))


def _validate_direct_participants(*, created_by, recipient):
    if not getattr(created_by, "is_authenticated", False) or not created_by.is_active:
        raise PermissionDenied("Un Profil actif et authentifié est requis.")
    try:
        sender_profile = created_by.profile
    except UserProfile.DoesNotExist as exc:
        raise PermissionDenied("Le Profil expéditeur est indisponible.") from exc
    if recipient is None or not recipient.user.is_active:
        raise ValidationError({"recipient": "Ce Profil n’est pas disponible."})
    if sender_profile.pk == recipient.pk:
        raise ValidationError({"recipient": "Vous ne pouvez pas vous partager ce contenu à vous-même."})
    return sender_profile


def _sender_name(user):
    return user.full_name or user.username or "Une personne"


def _delivery_message(envelope):
    if envelope.subject_type == ShareSubjectType.OPPORTUNITY:
        return "opportunité"
    if envelope.subject_type == ShareSubjectType.JOURNEY:
        return "parcours"
    return "activité"


def _create_delivery(*, envelope, recipient):
    delivery = ShareDelivery.objects.create(envelope=envelope, recipient=recipient)
    if envelope.subject_type == ShareSubjectType.JOURNEY:
        message = f"{_sender_name(envelope.created_by)} vous permet de repartir de son parcours."
    else:
        message = f"{_sender_name(envelope.created_by)} vous a partagé une {_delivery_message(envelope)}."
    create_notification(
        recipient=recipient.user,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SERVICE,
        title="Un partage Makolo pour vous",
        message=message,
        action_url=reverse("sharing:delivery", kwargs={"delivery_id": delivery.pk}),
        dedup_key=f"sharing-delivery:{delivery.pk}",
        metadata={"share_delivery_id": str(delivery.pk)},
        queue_email=False,
    )
    return delivery


@transaction.atomic
def create_direct_activity_share(*, created_by, recipient, activity, occurrence=None, intent=ShareIntent.VIEW, expires_at=None):
    _validate_direct_participants(created_by=created_by, recipient=recipient)
    envelope = _create_activity_envelope(
        created_by=created_by,
        activity=activity,
        occurrence=occurrence,
        intent=intent,
        expires_at=expires_at,
    )
    return CreatedDirectShare(envelope=envelope, delivery=_create_delivery(envelope=envelope, recipient=recipient))


@transaction.atomic
def create_direct_opportunity_share(*, created_by, recipient, opportunity_revision, intent=ShareIntent.VIEW, expires_at=None):
    _validate_direct_participants(created_by=created_by, recipient=recipient)
    envelope = _create_opportunity_envelope(
        created_by=created_by,
        opportunity_revision=opportunity_revision,
        intent=intent,
        expires_at=expires_at,
    )
    return CreatedDirectShare(envelope=envelope, delivery=_create_delivery(envelope=envelope, recipient=recipient))


def resolve_share_link(raw_token: str):
    link = ShareLink.objects.select_related("envelope").filter(token_hash=token_digest(raw_token)).first()
    if link is None or not link.envelope.is_active_at():
        raise ShareUnavailable
    return link.envelope


def resolve_activity_share_subject(envelope):
    if envelope.subject_type != ShareSubjectType.ACTIVITY:
        raise ShareUnavailable
    try:
        subject = envelope.activity_subject
    except ActivityShareSubject.DoesNotExist as exc:
        raise ShareUnavailable from exc
    if subject.activity_id is None:
        raise ShareUnavailable
    activity = publicly_visible_activities().filter(pk=subject.activity_id).first()
    if activity is None:
        raise ShareUnavailable
    occurrence = None
    if subject.occurrence_id is not None:
        try:
            occurrence = get_public_occurrence(subject.occurrence_id)
        except Occurrence.DoesNotExist as exc:
            raise ShareUnavailable from exc
        if occurrence.activity_id != activity.pk:
            raise ShareUnavailable
    return subject, activity, occurrence


def resolve_opportunity_share_subject(envelope):
    if envelope.subject_type != ShareSubjectType.OPPORTUNITY:
        raise ShareUnavailable
    try:
        subject = envelope.opportunity_subject
    except OpportunityShareSubject.DoesNotExist as exc:
        raise ShareUnavailable from exc
    shared_revision = subject.opportunity_revision
    if shared_revision is None:
        raise ShareUnavailable
    opportunity = published_opportunities().filter(pk=shared_revision.opportunity_id).first()
    if opportunity is None or opportunity.current_revision_id is None:
        raise ShareUnavailable
    return subject, opportunity, shared_revision, opportunity.current_revision


def resolve_delivery_for_recipient(*, delivery_id, user, mark_opened=False):
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    try:
        profile = user.profile
    except UserProfile.DoesNotExist as exc:
        raise PermissionDenied("Profil indisponible.") from exc
    delivery = (
        ShareDelivery.objects.select_related("envelope", "recipient", "recipient__user", "envelope__created_by")
        .filter(pk=delivery_id, recipient=profile)
        .first()
    )
    if delivery is None:
        raise PermissionDenied("Ce partage n’est pas disponible pour ce compte.")
    if not delivery.envelope.is_active_at():
        raise ShareUnavailable
    if delivery.envelope.subject_type == ShareSubjectType.ACTIVITY:
        resolve_activity_share_subject(delivery.envelope)
    elif delivery.envelope.subject_type == ShareSubjectType.OPPORTUNITY:
        resolve_opportunity_share_subject(delivery.envelope)
    elif delivery.envelope.subject_type == ShareSubjectType.JOURNEY:
        from .journey_reuse import resolve_journey_share_subject

        resolve_journey_share_subject(delivery.envelope)
    else:
        raise ShareUnavailable
    if mark_opened and delivery.opened_at is None:
        now = timezone.now()
        ShareDelivery.objects.filter(pk=delivery.pk, opened_at__isnull=True).update(opened_at=now)
        delivery.opened_at = now
    return delivery


@transaction.atomic
def accept_share_delivery(*, delivery_id, user):
    delivery = resolve_delivery_for_recipient(delivery_id=delivery_id, user=user)
    if delivery.envelope.subject_type == ShareSubjectType.JOURNEY:
        raise ValidationError("Utilisez l’acceptation Journey dédiée pour ce partage.")
    if delivery.declined_at:
        raise ValidationError("Ce partage a déjà été ignoré.")
    if delivery.accepted_at is None:
        delivery.accepted_at = timezone.now()
        delivery.save(update_fields=["accepted_at"])
    return delivery


@transaction.atomic
def decline_share_delivery(*, delivery_id, user):
    delivery = resolve_delivery_for_recipient(delivery_id=delivery_id, user=user)
    if delivery.accepted_at:
        raise ValidationError("Ce partage a déjà été utilisé.")
    if delivery.declined_at is None:
        delivery.declined_at = timezone.now()
        delivery.save(update_fields=["declined_at"])
    return delivery


@transaction.atomic
def revoke_share_link(*, envelope, actor=None):
    if actor is not None:
        allowed = bool(
            getattr(actor, "is_authenticated", False)
            and (getattr(actor, "is_staff", False) or envelope.created_by_id == actor.pk)
        )
        if not allowed:
            raise PermissionDenied("Vous ne pouvez pas révoquer ce partage.")
    if envelope.status == ShareStatus.REVOKED:
        return envelope
    envelope.status = ShareStatus.REVOKED
    envelope.revoked_at = timezone.now()
    envelope.save(update_fields=["status", "revoked_at", "updated_at"])
    return envelope

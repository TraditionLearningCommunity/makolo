from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from activities.models import Occurrence
from activities.selectors import publicly_visible_activities
from discovery.search import get_public_occurrence
from opportunities.selectors import published_opportunities

from .models import (
    ActivityShareSubject,
    OpportunityShareSubject,
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


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def share_public_url(raw_token: str) -> str:
    return f"{settings.MAKOLO_PUBLIC_BASE_URL}{reverse('sharing:landing', kwargs={'token': raw_token})}"


def share_qr_url(raw_token: str) -> str:
    return f"{settings.MAKOLO_PUBLIC_BASE_URL}{reverse('sharing:qr', kwargs={'token': raw_token})}"


def _validate_expiry(expires_at):
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError({"expires_at": "L’expiration doit être future."})


def _create_envelope_and_link(*, created_by, subject_type, intent, expires_at=None):
    _validate_expiry(expires_at)
    envelope = ShareEnvelope.objects.create(
        created_by=created_by,
        subject_type=subject_type,
        intent=intent,
        expires_at=expires_at,
    )
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    ShareLink.objects.create(envelope=envelope, token_hash=token_digest(raw_token))
    return CreatedShare(envelope=envelope, raw_token=raw_token)


@transaction.atomic
def create_activity_share(
    *,
    created_by,
    activity,
    occurrence=None,
    intent=ShareIntent.VIEW,
    expires_at=None,
):
    if intent not in ACTIVITY_INTENTS:
        raise ValidationError({"intent": "Cette intention n’est pas supportée pour une Activity."})
    if intent == ShareIntent.PARTICIPATE and occurrence is None:
        raise ValidationError({"intent": "Participer exige une Occurrence précise."})
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L’Occurrence doit appartenir à l’Activity partagée."})
    if not publicly_visible_activities().filter(pk=activity.pk).exists():
        raise ValidationError("Cette Activity n’est pas partageable publiquement.")
    if occurrence is not None:
        try:
            public_occurrence = get_public_occurrence(occurrence.pk)
        except Occurrence.DoesNotExist as exc:
            raise ValidationError("Cette Occurrence n’est pas partageable publiquement.") from exc
        if public_occurrence.activity_id != activity.pk:
            raise ValidationError({"occurrence": "Le contexte Activity/Occurrence est incohérent."})
        occurrence = public_occurrence
    created = _create_envelope_and_link(
        created_by=created_by,
        subject_type=ShareSubjectType.ACTIVITY,
        intent=intent,
        expires_at=expires_at,
    )
    ActivityShareSubject.objects.create(
        envelope=created.envelope,
        activity=activity,
        occurrence=occurrence,
    )
    return created


@transaction.atomic
def create_opportunity_share(
    *,
    created_by,
    opportunity_revision,
    intent=ShareIntent.VIEW,
    expires_at=None,
):
    if intent not in OPPORTUNITY_INTENTS:
        raise ValidationError({"intent": "Cette intention n’est pas supportée pour une Opportunity."})
    opportunity = (
        published_opportunities()
        .filter(pk=opportunity_revision.opportunity_id)
        .first()
    )
    if opportunity is None or opportunity.current_revision_id != opportunity_revision.pk:
        raise ValidationError("Seule la révision publiée courante peut être partagée.")
    created = _create_envelope_and_link(
        created_by=created_by,
        subject_type=ShareSubjectType.OPPORTUNITY,
        intent=intent,
        expires_at=expires_at,
    )
    OpportunityShareSubject.objects.create(
        envelope=created.envelope,
        opportunity_revision=opportunity_revision,
    )
    return created


def resolve_share_link(raw_token: str):
    link = (
        ShareLink.objects.select_related("envelope")
        .filter(token_hash=token_digest(raw_token))
        .first()
    )
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

"""Passport issuance is not Sharing. A grant refers to one issued document."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.db import transaction
from django.utils import timezone

from organizations.permissions import user_can_manage_organization
from domain_events.contracts import DomainEventType
from .analytics import emit_share_event

from .models import (
    PassportShareSubject, PublicSubjectKind, ShareIntent,
    ShareSubjectType, ShareDelivery, ShareStatus,
)
from .passport_documents import snapshot_payload_is_intact
from .services import (
    ShareUnavailable, _attach_link, _create_envelope, resolve_share_link,
    revoke_share_link, _validate_direct_participants, _create_delivery,
    _emit_created, DIRECT_DUPLICATE_WINDOW,
)


def _assert_can_share(snapshot, actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour partager votre Passeport.")
    if snapshot.subject_kind == PublicSubjectKind.PROFILE:
        authorized = snapshot.profile_id == actor.pk
    else:
        authorized = bool(
            snapshot.space_id
            and user_can_manage_organization(actor, snapshot.space)
        )
    if not authorized:
        raise PermissionDenied("Partage du Passeport non autorisé.")
    if snapshot.variant == "complete":
        raise ValidationError(
            "Le Passeport complet n'est pas partageable par lien : "
            "émettez une sélection publique, thématique ou personnalisée."
        )
    if snapshot.is_revoked or not snapshot_payload_is_intact(snapshot):
        raise ValidationError("Ce document n'est plus partageable.")


@transaction.atomic
def create_passport_share(*, snapshot, actor, days=7):
    """Explicit, bounded, revocable view grant to one previously issued document."""
    _assert_can_share(snapshot, actor)
    if isinstance(days, bool) or days not in (1, 7, 30):
        raise ValidationError("Choisissez une durée de 1, 7 ou 30 jours.")
    envelope = _create_envelope(
        created_by=actor,
        subject_type=ShareSubjectType.PASSPORT,
        intent=ShareIntent.VIEW,
        expires_at=timezone.now() + timedelta(days=days),
    )
    PassportShareSubject.objects.create(envelope=envelope, snapshot=snapshot)
    raw_token = _attach_link(envelope)
    emit_share_event(
        event_type=DomainEventType.SHARE_CREATED,
        envelope=envelope,
        idempotency_suffix="created",
        channel="passport_issued_link",
    )
    return envelope, (
        f"{settings.MAKOLO_PUBLIC_BASE_URL.rstrip('/')}"
        f"{reverse('sharing:passport-shared', kwargs={'token': raw_token})}"
    )


@transaction.atomic
def create_direct_passport_share(*, snapshot, actor, recipient, days=7):
    """Share one issued non-complete version with one Makolo recipient."""
    _assert_can_share(snapshot, actor)
    _validate_direct_participants(created_by=actor, recipient=recipient)
    if isinstance(days, bool) or days not in (1, 7, 30):
        raise ValidationError("Durée de partage invalide.")
    cutoff = timezone.now() - DIRECT_DUPLICATE_WINDOW
    existing = ShareDelivery.objects.filter(
        envelope__created_by=actor,
        envelope__subject_type=ShareSubjectType.PASSPORT,
        envelope__status=ShareStatus.ACTIVE,
        envelope__passport_subject__snapshot=snapshot,
        recipient=recipient,
        delivered_at__gte=cutoff,
    ).order_by("-delivered_at").first()
    if existing is not None and existing.envelope.is_active_at():
        return existing
    envelope = _create_envelope(
        created_by=actor,
        subject_type=ShareSubjectType.PASSPORT,
        intent=ShareIntent.VIEW,
        expires_at=timezone.now() + timedelta(days=days),
    )
    PassportShareSubject.objects.create(envelope=envelope, snapshot=snapshot)
    _emit_created(envelope, channel="direct_makolo")
    return _create_delivery(envelope=envelope, recipient=recipient)



def resolve_passport_share(token):
    """The bearer may read only the frozen, explicitly issued content."""
    envelope = resolve_share_link(token)
    if envelope.subject_type != ShareSubjectType.PASSPORT:
        raise ShareUnavailable
    try:
        snapshot = envelope.passport_subject.snapshot
    except PassportShareSubject.DoesNotExist as exc:
        raise ShareUnavailable from exc
    if snapshot.is_revoked or not snapshot_payload_is_intact(snapshot):
        raise ShareUnavailable
    if snapshot.variant == "complete":
        raise ShareUnavailable
    return envelope, snapshot


def revoke_passport_share(*, envelope, actor):
    if envelope.subject_type != ShareSubjectType.PASSPORT:
        raise ShareUnavailable
    snapshot = envelope.passport_subject.snapshot
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour révoquer un partage.")
    if snapshot.subject_kind == PublicSubjectKind.PROFILE:
        authorized = snapshot.profile_id == actor.pk
    else:
        authorized = bool(
            snapshot.space_id
            and user_can_manage_organization(actor, snapshot.space)
        )
    if not authorized:
        raise PermissionDenied("Révocation du partage non autorisée.")
    # The owner may revoke any grant to their document, even if the document
    # itself has already been revoked.
    return revoke_share_link(envelope=envelope, actor=None)

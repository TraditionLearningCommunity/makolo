"""Direct, revocable Sharing grant for one immutable Space document version."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from space_assets.models import SpaceDocument, SpaceDocumentVersion
from space_assets.services import can_manage_documents

from .models import (
    ShareDelivery, ShareEnvelope, ShareIntent, ShareStatus,
    ShareSubjectType, SpaceDocumentShareSubject,
)
from .services import (
    DIRECT_DUPLICATE_WINDOW, ShareUnavailable,
    _create_delivery, _create_envelope, _emit_created,
    _validate_direct_participants, resolve_delivery_for_recipient,
    revoke_share_link,
)


@transaction.atomic
def share_space_document(*, actor, version, recipient, days=7):
    """One authenticated Makolo recipient; no public bearer-file link."""
    doc = SpaceDocument.objects.select_for_update().select_related("space").get(
        pk=version.document_id,
    )
    version = SpaceDocumentVersion.objects.get(pk=version.pk, document=doc)
    if doc.archived_at is not None or not can_manage_documents(actor, doc.space):
        raise PermissionDenied("Vous ne pouvez pas partager ce document.")
    _validate_direct_participants(created_by=actor, recipient=recipient)
    if type(days) is not int or days not in (1, 7, 30):
        raise ValidationError({"days": "Durée non autorisée."})
    window = timezone.now() - DIRECT_DUPLICATE_WINDOW
    previous = ShareDelivery.objects.select_related("envelope").filter(
        recipient=recipient, envelope__created_by=actor,
        envelope__subject_type=ShareSubjectType.SPACE_DOCUMENT,
        envelope__status=ShareStatus.ACTIVE,
        envelope__space_document_subject__version=version,
        delivered_at__gte=window,
    ).order_by("-delivered_at").first()
    if previous is not None and previous.envelope.is_active_at():
        return previous
    envelope = _create_envelope(
        created_by=actor, subject_type=ShareSubjectType.SPACE_DOCUMENT,
        intent=ShareIntent.VIEW,
        expires_at=timezone.now() + timedelta(days=days),
    )
    SpaceDocumentShareSubject.objects.create(envelope=envelope, version=version)
    _emit_created(envelope, channel="space_document_direct")
    return _create_delivery(envelope=envelope, recipient=recipient)


def space_document_delivery(*, user, delivery_id, mark_opened=False):
    """Each read uses Sharing's current expiry/revocation/recipient checks."""
    delivery = resolve_delivery_for_recipient(
        delivery_id=delivery_id, user=user, mark_opened=mark_opened,
    )
    if delivery.declined_at is not None:
        raise ShareUnavailable
    envelope = delivery.envelope
    if envelope.subject_type != ShareSubjectType.SPACE_DOCUMENT:
        raise ShareUnavailable
    try:
        version = envelope.space_document_subject.version
    except SpaceDocumentShareSubject.DoesNotExist as exc:
        raise ShareUnavailable from exc
    if version.document.archived_at is not None:
        raise ShareUnavailable
    return delivery, version


def revoke_space_document_share(*, actor, delivery_id):
    delivery = ShareDelivery.objects.select_related(
        "envelope", "envelope__space_document_subject__version__document__space",
    ).filter(pk=delivery_id, envelope__subject_type=ShareSubjectType.SPACE_DOCUMENT).first()
    if delivery is None:
        raise ShareUnavailable
    doc = delivery.envelope.space_document_subject.version.document
    if not can_manage_documents(actor, doc.space):
        raise PermissionDenied("Révocation non autorisée.")
    return revoke_share_link(envelope=delivery.envelope, actor=None)

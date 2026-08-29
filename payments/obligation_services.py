from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.collaboration_services import ensure_case_access, is_beneficiary

from .models import (
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)


TERMINAL_OBLIGATION_STATUSES = {
    PaymentObligationStatus.SATISFIED,
    PaymentObligationStatus.WAIVED,
    PaymentObligationStatus.EXPIRED,
    PaymentObligationStatus.CANCELLED,
    PaymentObligationStatus.REFUNDED,
}


def _actor_id(actor):
    return getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None


def _emit_obligation_event(obligation, event_type, suffix, payload=None):
    base = {
        "obligation_id": str(obligation.pk),
        "journey_id": str(obligation.journey_id),
        "reason": obligation.reason,
        "status": obligation.status,
    }
    base.update(payload or {})
    return emit_domain_event(
        event_type=event_type,
        source_type="payment_obligation",
        source_id=obligation.pk,
        idempotency_key=f"payment_obligation:{obligation.pk}:{suffix}"[:255],
        space_id=getattr(obligation.journey.activity, "space_id", None),
        activity_id=obligation.journey.activity_id,
        payload=base,
    )


def _emit_evidence_event(evidence, event_type, suffix):
    obligation = evidence.obligation
    return emit_domain_event(
        event_type=event_type,
        source_type="payment_evidence",
        source_id=evidence.pk,
        idempotency_key=f"payment_evidence:{evidence.pk}:{suffix}"[:255],
        space_id=getattr(obligation.journey.activity, "space_id", None),
        activity_id=obligation.journey.activity_id,
        payload={
            "evidence_id": str(evidence.pk),
            "obligation_id": str(obligation.pk),
            "journey_id": str(obligation.journey_id),
            "status": evidence.status,
        },
    )


def _validate_payee(*, payee_space=None, payee_profile=None, external_payee_name=""):
    external_payee_name = (external_payee_name or "").strip()
    count = int(bool(payee_space)) + int(bool(payee_profile)) + int(bool(external_payee_name))
    if count != 1:
        raise ValidationError("Une obligation exige exactement un bénéficiaire économique.")
    return external_payee_name


@transaction.atomic
def create_payment_obligation(
    *,
    journey,
    reason,
    label,
    amount,
    currency,
    processing_mode,
    created_by=None,
    commerce_order=None,
    step=None,
    payee_space=None,
    payee_profile=None,
    external_payee_name="",
    due_at=None,
    source_key=None,
):
    if source_key:
        existing = PaymentObligation.objects.select_related("journey", "commerce_order", "step").filter(source_key=source_key).first()
        if existing:
            if existing.journey_id != journey.pk:
                raise ValidationError("Cette clé de provenance appartient à une autre Journey.")
            return existing
    if reason not in PaymentObligationReason.values:
        raise ValidationError("Motif d’obligation inconnu.")
    if processing_mode not in PaymentObligationProcessingMode.values:
        raise ValidationError("Mode de traitement financier inconnu.")
    external_payee_name = _validate_payee(
        payee_space=payee_space,
        payee_profile=payee_profile,
        external_payee_name=external_payee_name,
    )
    if commerce_order is not None and commerce_order.journey_id != journey.pk:
        raise ValidationError("La CommerceOrder appartient à une autre Journey.")
    if step is not None and step.journey_id != journey.pk:
        raise ValidationError("La JourneyStep appartient à une autre Journey.")
    obligation = PaymentObligation(
        journey=journey,
        commerce_order=commerce_order,
        step=step,
        reason=reason,
        label=(label or "").strip(),
        amount=amount,
        currency=(currency or "USD").upper(),
        processing_mode=processing_mode,
        payee_space=payee_space,
        payee_profile=payee_profile,
        external_payee_name=external_payee_name,
        due_at=due_at,
        source_key=source_key or None,
        created_by=created_by if _actor_id(created_by) else None,
    )
    obligation.full_clean()
    try:
        obligation.save()
    except IntegrityError as exc:
        if source_key:
            existing = PaymentObligation.objects.filter(source_key=source_key).first()
            if existing:
                return existing
        raise ValidationError("Impossible de créer cette obligation de façon unique.") from exc
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_CREATED, "created")
    return obligation


@transaction.atomic
def create_commerce_payment_obligation(*, commerce_order, actor=None):
    from commerce.models import CommerceOrder, PaymentMode

    commerce_order = (
        CommerceOrder.objects.select_for_update(of=("self",))
        .select_related(
            "journey__activity__space",
            "journey__activity__owner_profile",
            "payee_space",
            "payee_profile",
        )
        .order_by()
        .get(pk=commerce_order.pk)
    )
    if commerce_order.total <= 0 or commerce_order.payment_mode == PaymentMode.NONE:
        raise ValidationError("Cette CommerceOrder ne porte aucune obligation provider payante.")

    payee_space = commerce_order.payee_space
    payee_profile = commerce_order.payee_profile
    if payee_space is None and payee_profile is None:
        # Expand-compatible legacy orders may predate explicit Commerce payees.
        # The canonical Activity owner is objective business data, not an invented payee.
        activity = commerce_order.journey.activity
        payee_space = activity.space
        if payee_space is None:
            payee_profile = activity.owner_profile
    if payee_space is None and payee_profile is None:
        raise ValidationError("La CommerceOrder ne permet pas de déterminer un bénéficiaire économique canonique.")

    return create_payment_obligation(
        journey=commerce_order.journey,
        commerce_order=commerce_order,
        reason=PaymentObligationReason.COMMERCE,
        label=f"Paiement {commerce_order.reference}",
        amount=commerce_order.total,
        currency=commerce_order.currency,
        processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
        payee_space=payee_space,
        payee_profile=payee_profile,
        created_by=actor,
        source_key=f"commerce:{commerce_order.pk}",
    )


def _save_obligation_status(obligation, *, status, satisfied_at=None):
    obligation.status = status
    obligation.satisfied_at = satisfied_at
    obligation._allow_status_transition = True
    obligation.save(update_fields=["status", "satisfied_at", "updated_at"])
    return obligation


@transaction.atomic
def mark_obligation_processing(*, obligation):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.PROCESSING:
        return obligation
    if obligation.status != PaymentObligationStatus.PENDING:
        raise ValidationError("Seule une obligation en attente peut passer en traitement.")
    return _save_obligation_status(obligation, status=PaymentObligationStatus.PROCESSING)


@transaction.atomic
def restore_obligation_pending(*, obligation):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.PENDING:
        return obligation
    if obligation.status != PaymentObligationStatus.PROCESSING:
        return obligation
    return _save_obligation_status(obligation, status=PaymentObligationStatus.PENDING)


@transaction.atomic
def satisfy_payment_obligation(*, obligation, source="payment"):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.SATISFIED:
        return obligation
    if obligation.status in {PaymentObligationStatus.WAIVED, PaymentObligationStatus.EXPIRED, PaymentObligationStatus.CANCELLED, PaymentObligationStatus.REFUNDED}:
        raise ValidationError("Cette obligation est terminale et ne peut pas être satisfaite.")
    now = timezone.now()
    _save_obligation_status(obligation, status=PaymentObligationStatus.SATISFIED, satisfied_at=now)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_SATISFIED, f"satisfied:{source}")
    return obligation


@transaction.atomic
def refund_payment_obligation(*, obligation):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.status == PaymentObligationStatus.REFUNDED:
        return obligation
    if obligation.status != PaymentObligationStatus.SATISFIED:
        raise ValidationError("Seule une obligation satisfaite peut devenir remboursée.")
    _save_obligation_status(obligation, status=PaymentObligationStatus.REFUNDED, satisfied_at=None)
    _emit_obligation_event(obligation, DomainEventType.PAYMENT_OBLIGATION_REFUNDED, "refunded")
    return obligation


@transaction.atomic
def submit_payment_evidence(*, obligation, artifact, actor, paid_at, external_reference=""):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("journey__activity").get(pk=obligation.pk)
    if obligation.processing_mode != PaymentObligationProcessingMode.EXTERNAL:
        raise ValidationError("Une preuve externe exige une obligation processing_mode=external.")
    if obligation.status in TERMINAL_OBLIGATION_STATUSES:
        raise ValidationError("Cette obligation n’accepte plus de nouvelle preuve.")
    if artifact.journey_id != obligation.journey_id:
        raise ValidationError("Le reçu appartient à une autre Journey.")
    if not is_beneficiary(actor, obligation.journey):
        ensure_case_access(actor, obligation.journey, write=True)
    evidence = PaymentEvidence(
        obligation=obligation,
        artifact=artifact,
        external_reference=(external_reference or "").strip(),
        paid_at=paid_at,
        submitted_by=actor if _actor_id(actor) else None,
    )
    evidence.save()
    _emit_evidence_event(evidence, DomainEventType.PAYMENT_EVIDENCE_SUBMITTED, "submitted")
    return evidence


def _ensure_evidence_reviewer(actor, obligation):
    if getattr(actor, "is_staff", False):
        return
    ensure_case_access(actor, obligation.journey, write=True)


@transaction.atomic
def verify_payment_evidence(*, evidence, actor, review_note=""):
    evidence = (
        PaymentEvidence.objects.select_for_update(of=("self",))
        .select_related("obligation__journey__activity", "artifact")
        .get(pk=evidence.pk)
    )
    _ensure_evidence_reviewer(actor, evidence.obligation)
    if evidence.status == PaymentEvidenceStatus.VERIFIED:
        return evidence
    if evidence.status != PaymentEvidenceStatus.SUBMITTED:
        raise ValidationError("Seule une preuve soumise peut être vérifiée.")
    if evidence.obligation.status == PaymentObligationStatus.SATISFIED:
        raise ValidationError("L’obligation est déjà satisfaite par une autre preuve ou transaction.")
    now = timezone.now()
    evidence.status = PaymentEvidenceStatus.VERIFIED
    evidence.verified_by = actor if _actor_id(actor) else None
    evidence.verified_at = now
    evidence.review_note = (review_note or "")[:2000]
    evidence._allow_status_transition = True
    evidence.save()
    satisfy_payment_obligation(obligation=evidence.obligation, source=f"evidence:{evidence.pk}")
    _emit_evidence_event(evidence, DomainEventType.PAYMENT_EVIDENCE_VERIFIED, "verified")
    return evidence


@transaction.atomic
def reject_payment_evidence(*, evidence, actor, review_note=""):
    evidence = (
        PaymentEvidence.objects.select_for_update(of=("self",))
        .select_related("obligation__journey__activity", "artifact")
        .get(pk=evidence.pk)
    )
    _ensure_evidence_reviewer(actor, evidence.obligation)
    if evidence.status == PaymentEvidenceStatus.REJECTED:
        return evidence
    if evidence.status != PaymentEvidenceStatus.SUBMITTED:
        raise ValidationError("Seule une preuve soumise peut être rejetée.")
    if evidence.obligation.status == PaymentObligationStatus.SATISFIED:
        raise ValidationError("Une preuve ne peut plus être rejetée après satisfaction de l’obligation.")
    evidence.status = PaymentEvidenceStatus.REJECTED
    evidence.verified_by = actor if _actor_id(actor) else None
    evidence.verified_at = timezone.now()
    evidence.review_note = (review_note or "")[:2000]
    evidence._allow_status_transition = True
    evidence.save()
    _emit_evidence_event(evidence, DomainEventType.PAYMENT_EVIDENCE_REJECTED, "rejected")
    return evidence

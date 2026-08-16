import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import AccessStatus
from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
from domain_events.contracts import DomainEventType
from events.permissions import user_can_manage_event_finance
from tickets.models import TicketOrder, TicketStatus
from tickets.permissions import user_can_access_order
from tickets.services import _confirm_locked_order, cancel_order

from .commerce_bridge import sync_payment_commerce
from .domain_events import emit_payment_domain_event
from .models import Payment, PaymentEvent, PaymentProvider, PaymentStatus, Refund, RefundStatus


@dataclass(frozen=True)
class WebhookOutcome:
    event: PaymentEvent
    payment: Payment | None
    duplicate: bool = False


def _sandbox_enabled() -> bool:
    return bool(getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False))


def _payment_actor_can_initiate(actor, order: TicketOrder) -> bool:
    return user_can_access_order(actor, order)


def _commerce_payment_actor_can_initiate(actor, order: CommerceOrder) -> bool:
    if not getattr(actor, "is_authenticated", False):
        return False
    return bool(getattr(actor, "is_staff", False) or order.buyer_id == actor.pk)


def _payment_actor_can_manage(actor, payment: Payment) -> bool:
    if payment.order_id:
        return user_can_manage_event_finance(actor, payment.order.event)
    return bool(getattr(actor, "is_authenticated", False) and getattr(actor, "is_staff", False))


def _validate_provider(*, provider, actor, event=None):
    if provider not in PaymentProvider.values:
        raise ValidationError("Fournisseur de paiement non pris en charge.")
    if provider == PaymentProvider.SANDBOX and not _sandbox_enabled():
        raise ValidationError("Le fournisseur sandbox est désactivé.")
    if provider == PaymentProvider.MANUAL:
        if event is not None:
            if not user_can_manage_event_finance(actor, event):
                raise PermissionDenied("Seul un responsable finance, propriétaire, admin ou staff peut enregistrer un paiement manuel.")
        elif not getattr(actor, "is_staff", False):
            raise PermissionDenied("Un paiement manuel Commerce requiert une autorité financière explicite.")


@transaction.atomic
def initiate_payment(*, order: TicketOrder, actor, provider: str, method: str, payer_name: str = "", payer_email: str = "", payer_phone: str = "", idempotency_key: str | None = None) -> Payment:
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.order_id != order.pk:
                raise ValidationError("Cette clé d’idempotence appartient à une autre commande.")
            return existing

    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related(
            "event__activity",
            "event__activity__created_by",
            "event__activity__space",
            "buyer",
            "commerce_order",
        )
        .get(pk=order.pk)
    )
    if not _payment_actor_can_initiate(actor, order):
        raise PermissionDenied("Vous ne pouvez pas initier le paiement de cette commande.")
    if order.is_expired:
        raise ValidationError("Cette commande a expiré.")

    commerce_order = order.commerce_order
    if commerce_order is None:
        from tickets.commerce_capacity_bridge import sync_order_commerce
        commerce_order = sync_order_commerce(order)
    if commerce_order is None:
        raise ValidationError("Cette commande Event n’a pas de CommerceOrder canonique.")
    if commerce_order.status != CommerceOrderStatus.PENDING:
        raise ValidationError("Seule une commande en attente peut être payée.")
    if commerce_order.total <= 0 or commerce_order.payment_mode == PaymentMode.NONE:
        raise ValidationError("Cette commande est gratuite et ne nécessite aucun paiement.")
    if Payment.objects.filter(commerce_order=commerce_order, status=PaymentStatus.SUCCEEDED).exists():
        raise ValidationError("Cette commande possède déjà un paiement réussi.")
    _validate_provider(provider=provider, actor=actor, event=order.event)

    payment = Payment(
        order=order,
        commerce_order=commerce_order,
        initiated_by=actor if getattr(actor, "is_authenticated", False) else None,
        provider=provider,
        method=method,
        amount=commerce_order.total,
        currency=commerce_order.currency,
        payer_name=(payer_name or order.customer_name).strip(),
        payer_email=(payer_email or order.customer_email).strip().lower(),
        payer_phone=payer_phone.strip(),
        idempotency_key=idempotency_key or None,
        metadata={"source": "makolo-event-compat"},
    )
    payment.full_clean()
    try:
        payment.save()
    except IntegrityError as exc:
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        raise ValidationError("Impossible de créer ce paiement de façon unique.") from exc
    return payment


@transaction.atomic
def initiate_commerce_payment(
    *,
    commerce_order: CommerceOrder,
    actor,
    provider: str,
    method: str,
    payer_name: str = "",
    payer_email: str = "",
    payer_phone: str = "",
    idempotency_key: str | None = None,
) -> Payment:
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.commerce_order_id != commerce_order.pk:
                raise ValidationError("Cette clé d’idempotence appartient à une autre commande Commerce.")
            return existing

    commerce_order = (
        CommerceOrder.objects.select_for_update(of=("self",))
        .select_related("buyer", "journey", "payee_space")
        .order_by()
        .get(pk=commerce_order.pk)
    )
    if not _commerce_payment_actor_can_initiate(actor, commerce_order):
        raise PermissionDenied("Vous ne pouvez pas initier le paiement de cette commande Commerce.")
    if commerce_order.status != CommerceOrderStatus.PENDING:
        raise ValidationError("Seule une commande Commerce en attente peut être payée.")
    if commerce_order.expires_at and commerce_order.expires_at <= timezone.now():
        raise ValidationError("Cette commande Commerce a expiré.")
    if commerce_order.total <= 0 or commerce_order.payment_mode == PaymentMode.NONE:
        raise ValidationError("Cette commande Commerce ne nécessite aucun paiement provider.")
    if commerce_order.payment_mode not in {
        PaymentMode.UPFRONT,
        PaymentMode.AFTER_APPROVAL,
        PaymentMode.LATER,
    }:
        raise ValidationError("Ce mode de paiement ne requiert pas de transaction provider immédiate.")
    if Payment.objects.filter(commerce_order=commerce_order, status=PaymentStatus.SUCCEEDED).exists():
        raise ValidationError("Cette commande Commerce possède déjà un paiement réussi.")
    _validate_provider(provider=provider, actor=actor)

    payer_default = commerce_order.buyer
    payment = Payment(
        order=None,
        commerce_order=commerce_order,
        initiated_by=actor,
        provider=provider,
        method=method,
        amount=commerce_order.total,
        currency=commerce_order.currency,
        payer_name=(payer_name or getattr(payer_default, "full_name", "") or getattr(payer_default, "username", "")).strip(),
        payer_email=(payer_email or getattr(payer_default, "email", "")).strip().lower(),
        payer_phone=payer_phone.strip(),
        idempotency_key=idempotency_key or None,
        metadata={"source": "commerce"},
    )
    payment.full_clean()
    try:
        payment.save()
    except IntegrityError as exc:
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        raise ValidationError("Impossible de créer ce paiement Commerce de façon unique.") from exc
    return payment


@transaction.atomic
def complete_payment(*, payment: Payment, provider_reference: str, source: str = "provider") -> Payment:
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order__event__activity", "commerce_order")
        .get(pk=payment.pk)
    )
    if payment.status == PaymentStatus.SUCCEEDED:
        return payment
    if payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED, PaymentStatus.REFUNDED}:
        raise ValidationError("Ce paiement est déjà dans un état terminal incompatible.")

    if payment.order_id:
        order = (
            TicketOrder.objects.select_for_update(of=("self",))
            .select_related("event__activity", "commerce_order", "journey")
            .get(pk=payment.order_id)
        )
        if not order.commerce_order_id:
            raise ValidationError("La commande Event n’a pas de CommerceOrder canonique.")
        if order.commerce_order.status != CommerceOrderStatus.PENDING:
            raise ValidationError("La commande n’est plus en attente de paiement.")
        if order.is_expired:
            raise ValidationError("La commande a expiré avant la confirmation du paiement.")
        if Payment.objects.filter(commerce_order=order.commerce_order, status=PaymentStatus.SUCCEEDED).exclude(pk=payment.pk).exists():
            raise ValidationError("Un autre paiement a déjà confirmé cette commande.")
        _confirm_locked_order(order)
    else:
        commerce_order = CommerceOrder.objects.select_for_update(of=("self",)).order_by().get(pk=payment.commerce_order_id)
        if commerce_order.status != CommerceOrderStatus.PENDING:
            raise ValidationError("La commande Commerce n’est plus en attente de paiement.")
        if commerce_order.expires_at and commerce_order.expires_at <= timezone.now():
            raise ValidationError("La commande Commerce a expiré avant la confirmation du paiement.")
        if Payment.objects.filter(commerce_order=commerce_order, status=PaymentStatus.SUCCEEDED).exclude(pk=payment.pk).exists():
            raise ValidationError("Un autre paiement a déjà confirmé cette commande Commerce.")

    provider_reference = provider_reference.strip()
    if not provider_reference:
        raise ValidationError("La référence fournisseur est obligatoire.")
    now = timezone.now()
    payment.status = PaymentStatus.SUCCEEDED
    payment.provider_reference = provider_reference
    payment.processed_at = now
    payment.succeeded_at = now
    payment.failure_code = ""
    payment.failure_message = ""
    payment.metadata = {**payment.metadata, "completion_source": source}
    try:
        payment.save(update_fields=["status", "provider_reference", "processed_at", "succeeded_at", "failure_code", "failure_message", "metadata", "updated_at"])
    except IntegrityError as exc:
        raise ValidationError("Référence fournisseur déjà utilisée ou commande déjà payée.") from exc
    emit_payment_domain_event(payment, event_type=DomainEventType.PAYMENT_SUCCEEDED)
    sync_payment_commerce(payment)
    return payment


@transaction.atomic
def fail_payment(*, payment: Payment, failure_code: str = "", failure_message: str = "", provider_reference: str = "", source: str = "provider") -> Payment:
    payment = Payment.objects.select_for_update(of=("self",)).select_related("order", "order__event__activity", "commerce_order").get(pk=payment.pk)
    if payment.status == PaymentStatus.FAILED:
        return payment
    if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
        raise ValidationError("Un paiement réussi ne peut pas être marqué comme échoué.")
    if payment.status == PaymentStatus.CANCELLED:
        return payment
    now = timezone.now()
    payment.status = PaymentStatus.FAILED
    payment.failure_code = failure_code[:120]
    payment.failure_message = failure_message[:500]
    payment.provider_reference = provider_reference.strip()
    payment.processed_at = now
    payment.failed_at = now
    payment.metadata = {**payment.metadata, "failure_source": source}
    payment.save(update_fields=["status", "failure_code", "failure_message", "provider_reference", "processed_at", "failed_at", "metadata", "updated_at"])
    emit_payment_domain_event(payment, event_type=DomainEventType.PAYMENT_FAILED)
    return payment


@transaction.atomic
def cancel_payment(*, payment: Payment, actor) -> Payment:
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order", "order__event__activity", "order__buyer", "commerce_order", "commerce_order__buyer")
        .get(pk=payment.pk)
    )
    if payment.order_id:
        allowed = user_can_access_order(actor, payment.order)
    else:
        allowed = _commerce_payment_actor_can_initiate(actor, payment.commerce_order)
    if not allowed:
        raise PermissionDenied("Vous ne pouvez pas annuler ce paiement.")
    if payment.status == PaymentStatus.CANCELLED:
        return payment
    if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
        raise ValidationError("Un paiement réussi doit être remboursé, pas annulé.")
    if payment.status == PaymentStatus.FAILED:
        return payment
    payment.status = PaymentStatus.CANCELLED
    payment.cancelled_at = timezone.now()
    payment.processed_at = payment.cancelled_at
    payment.save(update_fields=["status", "cancelled_at", "processed_at", "updated_at"])
    return payment


@transaction.atomic
def complete_sandbox_payment(*, payment: Payment, actor) -> Payment:
    if not _sandbox_enabled():
        raise ValidationError("Le sandbox de paiement est désactivé.")
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order", "order__event__activity", "order__buyer", "commerce_order", "commerce_order__buyer")
        .get(pk=payment.pk)
    )
    if payment.provider != PaymentProvider.SANDBOX:
        raise ValidationError("Ce paiement n’utilise pas le fournisseur sandbox.")
    allowed = user_can_access_order(actor, payment.order) if payment.order_id else _commerce_payment_actor_can_initiate(actor, payment.commerce_order)
    if not allowed:
        raise PermissionDenied("Vous ne pouvez pas valider ce paiement.")
    return complete_payment(payment=payment, provider_reference=f"SBX-{uuid.uuid4().hex[:20].upper()}", source="sandbox-ui")


@transaction.atomic
def complete_manual_payment(*, payment: Payment, actor, provider_reference: str = "") -> Payment:
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order", "order__event__activity", "commerce_order")
        .get(pk=payment.pk)
    )
    if payment.provider != PaymentProvider.MANUAL:
        raise ValidationError("Ce paiement n’est pas de type manuel.")
    if not _payment_actor_can_manage(actor, payment):
        raise PermissionDenied("Vous n'avez pas le droit de confirmer ce paiement manuel.")
    return complete_payment(payment=payment, provider_reference=provider_reference.strip() or f"MAN-{uuid.uuid4().hex[:20].upper()}", source="manual")


@transaction.atomic
def refund_payment(*, payment: Payment, actor, reason: str = "", idempotency_key: str | None = None) -> Refund:
    if idempotency_key:
        existing = Refund.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.payment_id != payment.pk:
                raise ValidationError("Cette clé d’idempotence appartient à un autre remboursement.")
            return existing

    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order", "order__event__activity", "commerce_order")
        .get(pk=payment.pk)
    )
    if not _payment_actor_can_manage(actor, payment):
        raise PermissionDenied("Vous ne pouvez pas rembourser ce paiement.")
    if payment.status == PaymentStatus.REFUNDED:
        existing = payment.refunds.filter(status=RefundStatus.SUCCEEDED).first()
        if existing:
            return existing
        raise ValidationError("Ce paiement est déjà remboursé.")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise ValidationError("Seul un paiement réussi peut être remboursé.")
    if payment.order_id and payment.order.tickets.filter(
        Q(access__status=AccessStatus.USED) | Q(access__isnull=True, status=TicketStatus.USED)
    ).exists():
        raise ValidationError("Un paiement contenant un billet déjà utilisé ne peut pas être remboursé.")

    refund = Refund(
        payment=payment,
        requested_by=actor,
        amount=payment.amount,
        currency=payment.currency,
        reason=reason.strip()[:500],
        idempotency_key=idempotency_key or None,
        provider_reference=f"RFD-{payment.provider.upper()}-{uuid.uuid4().hex[:16].upper()}",
    )
    refund.save()
    if payment.order_id:
        # ticket_order remains an Event compatibility pointer for callbacks and
        # refund UX; cancellation itself delegates to canonical owners.
        cancel_order(order=payment.order, actor=actor)
    now = timezone.now()
    refund.status = RefundStatus.SUCCEEDED
    refund.processed_at = now
    refund.save(update_fields=["status", "processed_at", "updated_at"])
    payment.status = PaymentStatus.REFUNDED
    payment.processed_at = now
    payment.save(update_fields=["status", "processed_at", "updated_at"])
    emit_payment_domain_event(payment, event_type=DomainEventType.PAYMENT_REFUNDED)
    sync_payment_commerce(payment)
    return refund


def verify_sandbox_signature(raw_body: bytes, signature: str) -> bool:
    secret = getattr(settings, "PAYMENTS_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def _safe_webhook_payload(payload: dict) -> dict:
    allowed = {"id", "type", "payment_reference", "provider_reference", "failure_code", "failure_message"}
    return {key: payload[key] for key in allowed if key in payload}


def _existing_webhook_outcome(*, event_id: str, payload_hash: str) -> WebhookOutcome | None:
    existing = (
        PaymentEvent.objects.filter(
            provider=PaymentProvider.SANDBOX,
            event_id=event_id,
        )
        .select_related("payment")
        .first()
    )
    if not existing:
        return None
    if not hmac.compare_digest(existing.payload_hash, payload_hash):
        raise ValidationError(
            "Identifiant d’événement webhook déjà utilisé avec un payload différent."
        )
    return WebhookOutcome(event=existing, payment=existing.payment, duplicate=True)


@transaction.atomic
def process_sandbox_webhook(*, raw_body: bytes, signature: str) -> WebhookOutcome:
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Payload webhook JSON invalide.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Payload webhook invalide.")

    event_id = str(payload.get("id", "")).strip()
    event_type = str(payload.get("type", "")).strip()
    if not event_id or not event_type:
        raise ValidationError("Le webhook doit contenir id et type.")

    if not verify_sandbox_signature(raw_body, signature):
        raise PermissionDenied("Signature webhook invalide.")

    existing_outcome = _existing_webhook_outcome(event_id=event_id, payload_hash=payload_hash)
    if existing_outcome:
        return existing_outcome

    try:
        with transaction.atomic():
            event = PaymentEvent.objects.create(
                provider=PaymentProvider.SANDBOX,
                event_id=event_id,
                event_type=event_type,
                signature_valid=True,
                payload_hash=payload_hash,
                payload=_safe_webhook_payload(payload),
            )
    except IntegrityError:
        concurrent_outcome = _existing_webhook_outcome(event_id=event_id, payload_hash=payload_hash)
        if concurrent_outcome:
            return concurrent_outcome
        raise ValidationError("Impossible d’enregistrer le webhook de façon unique.")

    payment_reference = str(payload.get("payment_reference", "")).strip()
    try:
        payment = Payment.objects.select_for_update().get(reference=payment_reference)
    except Payment.DoesNotExist as exc:
        event.processing_error = "Paiement introuvable."
        event.processed_at = timezone.now()
        event.save(update_fields=["processing_error", "processed_at"])
        raise ValidationError("Paiement introuvable.") from exc

    if payment.provider != PaymentProvider.SANDBOX:
        event.processing_error = "Fournisseur incompatible."
        event.processed_at = timezone.now()
        event.payment = payment
        event.save(update_fields=["payment", "processing_error", "processed_at"])
        raise ValidationError("Fournisseur incompatible avec ce webhook.")

    event.payment = payment
    try:
        if event_type == "payment.succeeded":
            complete_payment(payment=payment, provider_reference=str(payload.get("provider_reference", "")).strip() or f"SBX-WH-{event_id[:40]}", source="sandbox-webhook")
        elif event_type == "payment.failed":
            fail_payment(
                payment=payment,
                failure_code=str(payload.get("failure_code", "")),
                failure_message=str(payload.get("failure_message", "")),
                provider_reference=str(payload.get("provider_reference", "")),
                source="sandbox-webhook",
            )
        else:
            raise ValidationError("Type d’événement webhook non pris en charge.")
    except Exception as exc:
        event.processing_error = str(exc)[:500]
        event.processed_at = timezone.now()
        event.save(update_fields=["payment", "processing_error", "processed_at"])
        raise

    event.processed = True
    event.processed_at = timezone.now()
    event.save(update_fields=["payment", "processed", "processed_at"])
    payment.refresh_from_db()
    return WebhookOutcome(event=event, payment=payment)

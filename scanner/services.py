import hashlib
import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.core.signing import BadSignature, Signer
from django.db import IntegrityError, transaction
from django.utils import timezone

from events.models import Event, EventStatus
from tickets.models import QR_SIGNING_SALT, Ticket, TicketStatus

from .models import ScanLog, ScanResult
from .permissions import get_active_assignment, user_can_scan_event


@dataclass(frozen=True)
class ScanOutcome:
    result: str
    message: str
    log: ScanLog
    ticket: Ticket | None = None

    @property
    def accepted(self) -> bool:
        return self.result == ScanResult.ACCEPTED


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest() if token else ""


def _outcome_from_log(log: ScanLog) -> ScanOutcome:
    return ScanOutcome(
        result=log.result,
        message=log.message,
        log=log,
        ticket=log.ticket,
    )


def _create_log(
    *,
    event,
    scanner,
    assignment,
    result,
    message,
    token,
    ticket=None,
    client_reference="",
    gate="",
    metadata=None,
) -> ScanOutcome:
    log = ScanLog.objects.create(
        event=event,
        ticket=ticket,
        scanner=scanner,
        assignment=assignment,
        result=result,
        message=message,
        qr_fingerprint=_fingerprint(token),
        client_reference=client_reference,
        gate=gate or (assignment.label if assignment else ""),
        metadata=metadata or {},
    )
    return ScanOutcome(result=result, message=message, log=log, ticket=ticket)


@transaction.atomic
def scan_ticket(
    *,
    token: str,
    actor,
    event: Event,
    client_reference: str = "",
    gate: str = "",
    metadata: dict | None = None,
) -> ScanOutcome:
    """Validate and consume one ticket exactly once.

    The event and ticket rows are locked for the duration of the transaction.
    PostgreSQL is the production target for strong row-level concurrency.
    A conditional unique constraint on accepted scans provides a second database
    guard against two accepted access records for the same ticket.
    """
    event = Event.objects.select_for_update().get(pk=event.pk)

    if not user_can_scan_event(actor, event):
        raise PermissionDenied("Vous n’êtes pas autorisé à scanner cet événement.")

    assignment = get_active_assignment(actor, event)
    token = (token or "").strip()
    client_reference = (client_reference or "").strip()[:64]
    gate = (gate or "").strip()[:120]

    if client_reference:
        existing = (
            ScanLog.objects.select_related("ticket", "ticket__ticket_type")
            .filter(scanner=actor, client_reference=client_reference)
            .first()
        )
        if existing:
            return _outcome_from_log(existing)

    if event.status != EventStatus.PUBLISHED or timezone.now() >= event.end_at:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.EVENT_UNAVAILABLE,
            message="Cet événement n’accepte pas de contrôle d’accès actuellement.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    if not token or len(token) > 1024:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.INVALID_TOKEN,
            message="QR code invalide.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    try:
        raw_code = Signer(salt=QR_SIGNING_SALT).unsign(token)
        code = uuid.UUID(raw_code)
    except (BadSignature, ValueError, TypeError, AttributeError):
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.INVALID_TOKEN,
            message="QR code invalide ou altéré.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    try:
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("event", "ticket_type", "order", "owner")
            .get(code=code)
        )
    except Ticket.DoesNotExist:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.UNKNOWN_TICKET,
            message="Billet introuvable.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    if ticket.event_id != event.pk:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.WRONG_EVENT,
            message="Ce billet appartient à un autre événement.",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    if ticket.status == TicketStatus.USED:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.DUPLICATE,
            message="Billet déjà utilisé.",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    if ticket.status != TicketStatus.VALID or not ticket.is_valid:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.INVALID_STATUS,
            message=f"Billet non valide ({ticket.get_status_display()}).",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    now = timezone.now()
    ticket.status = TicketStatus.USED
    ticket.used_at = now
    ticket.save(update_fields=["status", "used_at", "updated_at"])

    try:
        with transaction.atomic():
            outcome = _create_log(
                event=event,
                scanner=actor,
                assignment=assignment,
                result=ScanResult.ACCEPTED,
                message="Accès autorisé.",
                token=token,
                ticket=ticket,
                client_reference=client_reference,
                gate=gate,
                metadata=metadata,
            )
    except IntegrityError:
        # Defensive fallback for an exceptional race or inconsistent legacy row.
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            result=ScanResult.DUPLICATE,
            message="Billet déjà accepté par un autre contrôle.",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    return outcome

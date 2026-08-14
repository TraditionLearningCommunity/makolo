import hashlib
import uuid
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.signing import BadSignature, Signer
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from access.models import AccessUseResult
from access.services import validate_access, validate_access_credential
from events.activity_bridge import sync_event_core
from events.models import Event, EventStatus
from tickets.journey_access_bridge import sync_ticket_access
from tickets.models import QR_SIGNING_SALT, Ticket, TicketStatus

from .models import EventAccessGate, ScanLog, ScanResult
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
    access_gate=None,
    metadata=None,
) -> ScanOutcome:
    gate_label = (
        (access_gate.name if access_gate else "")
        or gate
        or (assignment.label if assignment else "")
    )
    log = ScanLog.objects.create(
        event=event,
        ticket=ticket,
        scanner=scanner,
        assignment=assignment,
        access_gate=access_gate,
        result=result,
        message=message,
        qr_fingerprint=_fingerprint(token),
        client_reference=client_reference,
        gate=gate_label[:120],
        metadata=metadata or {},
    )
    return ScanOutcome(result=result, message=message, log=log, ticket=ticket)


def _resolve_access_gate(*, event, assignment, access_gate, gate_text):
    if access_gate is not None:
        if access_gate.event_id != event.pk:
            raise ValidationError("Cette porte appartient à un autre événement.")
        if assignment and assignment.access_gate_id and assignment.access_gate_id != access_gate.pk:
            raise PermissionDenied("Votre terminal est affecté à une autre porte.")
        return access_gate

    if assignment and assignment.access_gate_id:
        return assignment.access_gate

    gate_text = (gate_text or "").strip()
    if not gate_text:
        return None
    return EventAccessGate.objects.filter(event=event).filter(
        Q(name__iexact=gate_text) | Q(slug=gate_text)
    ).first()


def _scan_result_for_access(result):
    return {
        AccessUseResult.ACCEPTED: ScanResult.ACCEPTED,
        AccessUseResult.ALREADY_USED: ScanResult.DUPLICATE,
        AccessUseResult.WRONG_ACTIVITY: ScanResult.WRONG_EVENT,
        AccessUseResult.WRONG_OCCURRENCE: ScanResult.WRONG_EVENT,
        AccessUseResult.INVALID_CREDENTIAL: ScanResult.INVALID_TOKEN,
        AccessUseResult.EXPIRED: ScanResult.INVALID_STATUS,
        AccessUseResult.NOT_YET_VALID: ScanResult.INVALID_STATUS,
        AccessUseResult.REVOKED: ScanResult.INVALID_STATUS,
        AccessUseResult.CANCELLED: ScanResult.INVALID_STATUS,
    }[result]


def _message_for_access(result):
    return {
        AccessUseResult.ACCEPTED: "Accès autorisé.",
        AccessUseResult.ALREADY_USED: "Billet déjà utilisé.",
        AccessUseResult.WRONG_ACTIVITY: "Ce billet appartient à un autre événement.",
        AccessUseResult.WRONG_OCCURRENCE: "Ce billet appartient à une autre occurrence.",
        AccessUseResult.INVALID_CREDENTIAL: "QR code invalide ou altéré.",
        AccessUseResult.EXPIRED: "Billet expiré.",
        AccessUseResult.NOT_YET_VALID: "Billet pas encore valide.",
        AccessUseResult.REVOKED: "Billet révoqué.",
        AccessUseResult.CANCELLED: "Billet annulé.",
    }[result]


def _scanner_authority(event):
    return lambda controller, access: user_can_scan_event(controller, event)


def _sync_ticket_after_access_accept(ticket):
    if ticket is None or ticket.status == TicketStatus.USED:
        return
    now = timezone.now()
    ticket.status = TicketStatus.USED
    ticket.used_at = now
    ticket.save(update_fields=["status", "used_at", "updated_at"])


def _log_access_outcome(
    *,
    outcome,
    event,
    actor,
    assignment,
    token,
    ticket,
    client_reference,
    gate,
    effective_gate,
    metadata,
):
    if outcome.accepted:
        _sync_ticket_after_access_accept(ticket)
    result = _scan_result_for_access(outcome.result)
    return _create_log(
        event=event,
        scanner=actor,
        assignment=assignment,
        access_gate=effective_gate,
        result=result,
        message=_message_for_access(outcome.result),
        token=token,
        ticket=ticket,
        client_reference=client_reference,
        gate=gate,
        metadata=metadata,
    )


@transaction.atomic
def scan_ticket(
    *,
    token: str,
    actor,
    event: Event,
    client_reference: str = "",
    gate: str = "",
    access_gate: EventAccessGate | None = None,
    metadata: dict | None = None,
) -> ScanOutcome:
    """Validate an Event access through canonical Access while preserving Ticket UX.

    Access owns the single-use decision and row lock. ScanLog remains the
    Event-facing audit trail. Historical signed Ticket QR codes are accepted
    only while the linked Access has no AccessCredential; once a credential is
    issued/rotated the legacy representation can no longer bypass revocation.
    """
    event = Event.objects.select_related("activity").get(pk=event.pk)

    if not user_can_scan_event(actor, event):
        raise PermissionDenied("Vous n’êtes pas autorisé à scanner cet événement.")

    assignment = get_active_assignment(actor, event)
    token = (token or "").strip()
    client_reference = (client_reference or "").strip()[:64]
    gate = (gate or "").strip()[:120]
    effective_gate = _resolve_access_gate(
        event=event,
        assignment=assignment,
        access_gate=access_gate,
        gate_text=gate,
    )

    if client_reference:
        existing = (
            ScanLog.objects.select_related(
                "ticket",
                "ticket__ticket_type",
                "access_gate",
            )
            .filter(scanner=actor, client_reference=client_reference)
            .first()
        )
        if existing:
            return _outcome_from_log(existing)

    if effective_gate and not effective_gate.is_active:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
            result=ScanResult.GATE_UNAVAILABLE,
            message=f"La porte {effective_gate.name} est actuellement fermée.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    if event.status != EventStatus.PUBLISHED or timezone.now() >= event.end_at:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
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
            access_gate=effective_gate,
            result=ScanResult.INVALID_TOKEN,
            message="QR code invalide.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    activity, occurrence = sync_event_core(event)
    authority_check = _scanner_authority(event)

    canonical = validate_access_credential(
        token,
        controller=actor,
        authority_check=authority_check,
        expected_activity=activity,
        expected_occurrence=occurrence,
        source="scanner",
    )
    if canonical.result != AccessUseResult.INVALID_CREDENTIAL:
        ticket = None
        if canonical.access is not None:
            ticket = (
                Ticket.objects.select_related("ticket_type", "order", "owner")
                .filter(access=canonical.access)
                .first()
            )
        try:
            return _log_access_outcome(
                outcome=canonical,
                event=event,
                actor=actor,
                assignment=assignment,
                token=token,
                ticket=ticket,
                client_reference=client_reference,
                gate=gate,
                effective_gate=effective_gate,
                metadata=metadata,
            )
        except IntegrityError:
            return _create_log(
                event=event,
                scanner=actor,
                assignment=assignment,
                access_gate=effective_gate,
                result=ScanResult.DUPLICATE,
                message="Billet déjà accepté par un autre contrôle.",
                token=token,
                ticket=ticket,
                client_reference=client_reference,
                gate=gate,
                metadata=metadata,
            )

    # Controlled beta compatibility: resolve the former signed Ticket.code.
    try:
        raw_code = Signer(salt=QR_SIGNING_SALT).unsign(token)
        code = uuid.UUID(raw_code)
    except (BadSignature, ValueError, TypeError, AttributeError):
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
            result=ScanResult.INVALID_TOKEN,
            message="QR code invalide ou altéré.",
            token=token,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    try:
        ticket = (
            Ticket.objects.select_for_update(of=("self",))
            .select_related("event", "ticket_type", "order", "owner", "access")
            .order_by()
            .get(code=code)
        )
    except Ticket.DoesNotExist:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
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
            access_gate=effective_gate,
            result=ScanResult.WRONG_EVENT,
            message="Ce billet appartient à un autre événement.",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    access = ticket.access or sync_ticket_access(ticket)
    if access is not None:
        # Once the Access has any canonical credential, its old Ticket QR is no
        # longer an acceptable bearer representation. Rotation is therefore real.
        if access.credentials.exists():
            return _create_log(
                event=event,
                scanner=actor,
                assignment=assignment,
                access_gate=effective_gate,
                result=ScanResult.INVALID_TOKEN,
                message="Ce QR historique a été remplacé.",
                token=token,
                ticket=ticket,
                client_reference=client_reference,
                gate=gate,
                metadata=metadata,
            )
        outcome = validate_access(
            access=access,
            credential=None,
            controller=actor,
            authority_check=authority_check,
            expected_activity=activity,
            expected_occurrence=occurrence,
            source="scanner-legacy-ticket",
        )
        return _log_access_outcome(
            outcome=outcome,
            event=event,
            actor=actor,
            assignment=assignment,
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            effective_gate=effective_gate,
            metadata=metadata,
        )

    # Last compatibility branch for a beta guest Ticket that cannot be linked
    # deterministically to an individual Makolo Profile.
    if ticket.status == TicketStatus.USED:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
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
            access_gate=effective_gate,
            result=ScanResult.INVALID_STATUS,
            message=f"Billet non valide ({ticket.get_status_display()}).",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

    _sync_ticket_after_access_accept(ticket)
    try:
        with transaction.atomic():
            return _create_log(
                event=event,
                scanner=actor,
                assignment=assignment,
                access_gate=effective_gate,
                result=ScanResult.ACCEPTED,
                message="Accès autorisé.",
                token=token,
                ticket=ticket,
                client_reference=client_reference,
                gate=gate,
                metadata=metadata,
            )
    except IntegrityError:
        return _create_log(
            event=event,
            scanner=actor,
            assignment=assignment,
            access_gate=effective_gate,
            result=ScanResult.DUPLICATE,
            message="Billet déjà accepté par un autre contrôle.",
            token=token,
            ticket=ticket,
            client_reference=client_reference,
            gate=gate,
            metadata=metadata,
        )

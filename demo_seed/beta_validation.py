from __future__ import annotations

from datetime import timedelta

from access.models import Access, AccessStatus
from activities.models import ActivityStatus, ActivityVisibility, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.selectors import available_quantity
from commerce.models import CommerceOrder, Offer, PaymentMode
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import DeliveryStatus, NotificationDelivery
from organizations.models import OrganizationMembership
from payments.models import Payment
from scanner.models import ScannerAssignment
from tickets.models import Ticket, TicketOrder
from transport.models import TransportDeparture, TransportService

from .beta import BETA_PERSONAS


class BetaScenarioValidationError(RuntimeError):
    pass


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def assert_beta_scenario_coverage(*, as_of) -> dict[str, int]:
    """Read-only contract for the canonical beta dataset.

    Product scenarios are validated explicitly. Legacy/projection models are
    never fabricated merely to make a global model-coverage counter green.
    """
    from accounts.models import User
    from events.models import Event

    errors: list[str] = []
    personas = {user.email: user for user in User.objects.filter(email__in=BETA_PERSONAS.values())}
    _require(len(personas) == len(BETA_PERSONAS), "personas bêta incomplets", errors)

    event_occurrences = Occurrence.objects.filter(
        activity__event_vertical__isnull=False,
        activity__status=ActivityStatus.PUBLISHED,
        activity__visibility=ActivityVisibility.PUBLIC,
        status="scheduled",
        start_at__gt=as_of,
    ).distinct()
    transport_occurrences = Occurrence.objects.filter(
        activity__transport_service__isnull=False,
        activity__status=ActivityStatus.PUBLISHED,
        activity__visibility=ActivityVisibility.PUBLIC,
        status="scheduled",
        start_at__gt=as_of,
    ).distinct()
    _require(event_occurrences.count() >= 5, "pas assez d’Events publics futurs", errors)
    _require(transport_occurrences.count() >= 5, "pas assez de départs Transport futurs", errors)
    _require(event_occurrences.filter(start_at__gte=as_of + timedelta(days=28)).exists(), "horizon Event inférieur à quatre semaines", errors)
    _require(transport_occurrences.filter(start_at__gte=as_of + timedelta(days=28)).exists(), "horizon Transport inférieur à quatre semaines", errors)

    free_event_offer = Offer.objects.filter(activity__event_vertical__isnull=False, unit_price=0, payment_mode=PaymentMode.NONE, status="active").first()
    paid_event_offer = Offer.objects.filter(activity__event_vertical__isnull=False, unit_price__gt=0, payment_mode=PaymentMode.UPFRONT, status="active").first()
    _require(free_event_offer is not None, "scénario Event gratuit absent", errors)
    _require(paid_event_offer is not None, "scénario Event payant absent", errors)
    _require(Event.objects.filter(activity__status=ActivityStatus.PUBLISHED, activity__visibility=ActivityVisibility.PUBLIC, activity__offers__isnull=True).exists(), "Event public sans commerce absent", errors)

    transport_activity_ids = list(TransportService.objects.values_list("activity_id", flat=True))
    _require(bool(transport_activity_ids), "verticale Transport absente", errors)
    _require(not Event.objects.filter(activity_id__in=transport_activity_ids).exists(), "Transport dépend artificiellement d’Event", errors)
    _require(TransportDeparture.objects.count() >= 6, "pas assez de départs Transport", errors)
    _require(Offer.objects.filter(activity_id__in=transport_activity_ids, payment_mode=PaymentMode.UPFRONT, unit_price__gt=0).exists(), "Transport paiement en ligne absent", errors)
    _require(Offer.objects.filter(activity_id__in=transport_activity_ids, payment_mode=PaymentMode.ON_SITE, unit_price__gt=0).exists(), "Transport paiement sur place absent", errors)

    participant = personas.get(BETA_PERSONAS["participant"])
    if participant is not None:
        journeys = Journey.objects.filter(beneficiary=participant)
        _require(journeys.filter(activity__event_vertical__isnull=False).exists(), "Participant sans parcours Event", errors)
        _require(journeys.filter(activity__transport_service__isnull=False).exists(), "Participant sans parcours Transport", errors)
        _require(journeys.filter(status=JourneyStatus.DRAFT).exists(), "Participant sans démarche à continuer", errors)
        _require(journeys.filter(status=JourneyStatus.CONFIRMED).exists(), "Participant sans démarche confirmée", errors)
        _require(Access.objects.filter(beneficiary=participant, status=AccessStatus.VALID).exists(), "Participant sans billet valide", errors)
        _require(Access.objects.filter(beneficiary=participant, status=AccessStatus.USED).exists(), "Participant sans historique d’accès utilisé", errors)
        _require(journeys.filter(workflow=WorkflowKind.INVITATION, status=JourneyStatus.PENDING_APPROVAL).exists(), "invitation en attente absente", errors)

    if free_event_offer is not None:
        free_journeys = Journey.objects.filter(activity=free_event_offer.activity, workflow=WorkflowKind.REGISTRATION)
        _require(free_journeys.exists(), "Journey d’inscription gratuite absent", errors)
        _require(not Payment.objects.filter(commerce_order__journey__in=free_journeys).exists(), "Event gratuit ne doit pas créer de Payment", errors)

    _require(Payment.objects.filter(commerce_order__isnull=False, provider="sandbox", status="succeeded").exists(), "paiement sandbox canonique absent", errors)
    _require(not Payment.objects.filter(amount__lte=0).exists(), "Payment nul/invalide présent", errors)
    _require(CommerceOrder.objects.filter(payment_mode=PaymentMode.ON_SITE).exists(), "commande on-site absente", errors)
    _require(not Payment.objects.filter(commerce_order__payment_mode=PaymentMode.ON_SITE).exists(), "on-site ne doit pas être matérialisé comme Payment encaissé", errors)

    sold_out_event = False
    sold_out_transport = False
    for offer in Offer.objects.filter(status="active", capacity_pool__isnull=False).select_related("capacity_pool", "activity"):
        if available_quantity(offer.capacity_pool, now=as_of) == 0:
            sold_out_event = sold_out_event or hasattr(offer.activity, "event_vertical")
            sold_out_transport = sold_out_transport or hasattr(offer.activity, "transport_service")
    _require(sold_out_event, "Event complet non dérivé de Capacity", errors)
    _require(sold_out_transport, "Transport complet non dérivé de Capacity", errors)

    scanner = personas.get(BETA_PERSONAS["scanner"])
    event_scanner_assignment = ScannerAssignment.objects.filter(
        agent=scanner,
        event__isnull=False,
        is_active=True,
    ).select_related("activity").first() if scanner is not None else None
    transport_scanner_assignment = ScannerAssignment.objects.filter(
        agent=scanner,
        event__isnull=True,
        activity__transport_service__isnull=False,
        is_active=True,
    ).select_related("activity").first() if scanner is not None else None
    _require(event_scanner_assignment is not None, "scope scanner Event absent", errors)
    _require(transport_scanner_assignment is not None, "scope scanner Transport canonique absent", errors)
    _require(Access.objects.filter(source_key="beta:scanner-smoke-event", status=AccessStatus.VALID).exists(), "Access scanner Event dédié absent", errors)
    _require(Access.objects.filter(source_key="beta:scanner-smoke-transport", status=AccessStatus.VALID).exists(), "Access scanner Transport dédié absent", errors)

    _require(not NotificationDelivery.objects.filter(status__in=[DeliveryStatus.QUEUED, DeliveryStatus.PROCESSING]).exists(), "delivery externe en attente après seed", errors)
    _require(OrganizationMembership.objects.filter(user__email__in=BETA_PERSONAS.values()).count() == 0, "personas bêta dépendants d’OrganizationMembership legacy", errors)
    _require(TicketOrder.objects.count() == 0, "TicketOrder legacy peuplée par le profil bêta", errors)
    _require(Ticket.objects.count() == 0, "Ticket legacy peuplé par le profil bêta", errors)

    finance = personas.get(BETA_PERSONAS["finance"])
    event_manager = personas.get(BETA_PERSONAS["event_manager"])
    event_space = paid_event_offer.activity.space if paid_event_offer is not None else None
    if finance and event_space:
        _require(can(finance, PermissionCode.FINANCE_VIEW, space=event_space), "persona Finance sans permission Finance", errors)
        _require(not can(finance, PermissionCode.CRM_MANAGE, space=event_space), "persona Finance reçoit CRM par erreur", errors)
        _require(not can(finance, PermissionCode.ACCESS_MANAGE, space=event_space), "persona Finance reçoit Scanner/Access par erreur", errors)
    if event_manager and paid_event_offer is not None:
        _require(can(event_manager, PermissionCode.ACTIVITY_MANAGE, activity=paid_event_offer.activity), "Event manager sans autorité Activity", errors)
    if scanner and event_scanner_assignment is not None:
        _require(can(scanner, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=event_scanner_assignment.activity), "scanner sans autorité de contrôle Event", errors)
        _require(not can(scanner, PermissionCode.FINANCE_VIEW, space=event_scanner_assignment.activity.space), "scanner reçoit Finance par erreur", errors)
    if scanner and transport_scanner_assignment is not None:
        _require(can(scanner, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=transport_scanner_assignment.activity), "scanner sans autorité de contrôle Transport", errors)

    if errors:
        raise BetaScenarioValidationError("Validation bêta échouée: " + "; ".join(errors))

    return {
        "personas": len(personas),
        "future_event_occurrences": event_occurrences.count(),
        "future_transport_occurrences": transport_occurrences.count(),
        "journeys": Journey.objects.filter(initiated_by__email__in=BETA_PERSONAS.values()).count(),
        "orders": CommerceOrder.objects.filter(source_key__startswith="beta:").count(),
        "payments": Payment.objects.filter(metadata__seed="makolo-beta").count(),
        "accesses": Access.objects.filter(source_key__startswith="beta:").count(),
        "scanner_assignments": ScannerAssignment.objects.filter(agent__email=BETA_PERSONAS["scanner"]).count(),
    }

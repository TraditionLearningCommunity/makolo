from __future__ import annotations

from datetime import timedelta

from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import can
from capacity.models import CapacityPool
from capacity.selectors import available_quantity
from commerce.models import CommerceOrder, Offer, PaymentMode
from journeys.models import Journey, JourneyRequest, JourneyStatus, WorkflowKind
from notifications.models import DeliveryStatus, NotificationDelivery
from organizations.models import Organization, OrganizationMembership, TeamMembership
from payments.models import Payment
from scanner.models import ScannerAssignment
from tickets.models import Ticket, TicketOrder
from transport.models import TransportDeparture, TransportService

from .beta import BETA_PERSONAS
from .task22_extension import T22_PERSONAS


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
    expected_emails = set(BETA_PERSONAS.values()) | set(T22_PERSONAS.values())
    personas = {user.email: user for user in User.objects.filter(email__in=expected_emails)}
    _require(len(personas) == len(expected_emails), "personas bêta/T22 incomplets", errors)

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
    _require(Activity.objects.filter(pk__in=transport_activity_ids).exists(), "Activity Transport canonique absente", errors)
    _require(Occurrence.objects.filter(activity_id__in=transport_activity_ids).exists(), "Occurrence non Event absente", errors)
    _require(TransportDeparture.objects.count() >= 6, "pas assez de départs Transport", errors)
    _require(Offer.objects.filter(activity_id__in=transport_activity_ids, payment_mode=PaymentMode.UPFRONT, unit_price__gt=0).exists(), "Transport paiement en ligne absent", errors)
    _require(Offer.objects.filter(activity_id__in=transport_activity_ids, payment_mode=PaymentMode.ON_SITE, unit_price__gt=0).exists(), "Transport paiement sur place absent", errors)
    _require(CapacityPool.objects.filter(activity_id__in=transport_activity_ids).exists(), "Capacity Transport canonique absente", errors)
    _require(Journey.objects.filter(activity_id__in=transport_activity_ids).exists(), "Journey non Event absent", errors)
    _require(CommerceOrder.objects.filter(journey__activity_id__in=transport_activity_ids).exists(), "CommerceOrder non Event absente", errors)
    _require(Payment.objects.filter(commerce_order__journey__activity_id__in=transport_activity_ids).exists(), "Payment non Event absent", errors)
    _require(Access.objects.filter(activity_id__in=transport_activity_ids).exists(), "Access non Event absent", errors)
    _require(
        AccessUse.objects.filter(access__activity_id__in=transport_activity_ids, result=AccessUseResult.ACCEPTED).exists(),
        "AccessUse accepté non Event absent",
        errors,
    )

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

    _require(JourneyRequest.objects.filter(journey__activity__event_vertical__isnull=False).exists(), "JourneyRequest Event attendue absente", errors)

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
    _require(OrganizationMembership.objects.filter(user__email__in=expected_emails).count() == 0, "personas bêta dépendants d’OrganizationMembership legacy", errors)
    _require(TicketOrder.objects.count() == 0, "TicketOrder legacy peuplée par le profil bêta", errors)
    _require(Ticket.objects.count() == 0, "Ticket legacy peuplé par le profil bêta", errors)

    finance = personas.get(BETA_PERSONAS["finance"])
    marketing = personas.get(BETA_PERSONAS["marketing"])
    event_manager = personas.get(BETA_PERSONAS["event_manager"])
    owner = personas.get(T22_PERSONAS["owner"])
    admin = personas.get(T22_PERSONAS["admin"])
    access_manager = personas.get(T22_PERSONAS["access_manager"])
    activity_local = personas.get(T22_PERSONAS["activity_local"])
    team_only = personas.get(T22_PERSONAS["team_only"])
    staff = personas.get(BETA_PERSONAS["staff"])
    event_space = Organization.objects.filter(slug="beta-events").first()
    transport_space = Organization.objects.filter(slug="beta-transport").first()

    if owner and event_space:
        _require(can(owner, PermissionCode.SPACE_MANAGE, space=event_space), "Owner sans gestion Espace", errors)
        _require(can(owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space), "Owner sans gestion ownership", errors)
    if admin and event_space:
        _require(can(admin, PermissionCode.SPACE_MANAGE, space=event_space), "Admin sans administration Espace", errors)
        _require(not can(admin, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space), "Admin reçoit ownership par erreur", errors)
        _require(
            Mandate.objects.filter(profile=admin, space=event_space, role__code=SystemRoleCode.SPACE_ADMIN, status=MandateStatus.ACTIVE).exists(),
            "Admin sans Mandate space-admin actif",
            errors,
        )
    if finance and event_space:
        _require(can(finance, PermissionCode.FINANCE_VIEW, space=event_space), "persona Finance sans permission Finance", errors)
        _require(not can(finance, PermissionCode.CRM_MANAGE, space=event_space), "persona Finance reçoit CRM par erreur", errors)
        _require(not can(finance, PermissionCode.ACCESS_MANAGE, space=event_space), "persona Finance reçoit Scanner/Access par erreur", errors)
        _require(not can(finance, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space), "persona Finance reçoit ownership par erreur", errors)
    if marketing and event_space:
        _require(can(marketing, PermissionCode.MARKETING_MANAGE, space=event_space), "Marketing sans permission marketing", errors)
        _require(not can(marketing, PermissionCode.FINANCE_VIEW, space=event_space), "Marketing reçoit Finance par erreur", errors)
        _require(not can(marketing, PermissionCode.ACCESS_MANAGE, space=event_space), "Marketing reçoit Access par erreur", errors)
        _require(not can(marketing, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space), "Marketing reçoit ownership par erreur", errors)
    if access_manager and event_space:
        _require(can(access_manager, PermissionCode.ACCESS_MANAGE, space=event_space), "Access Manager sans permission Access", errors)
        _require(not can(access_manager, PermissionCode.FINANCE_VIEW, space=event_space), "Access Manager reçoit Finance par erreur", errors)
        _require(not can(access_manager, PermissionCode.SPACE_OWNERSHIP_MANAGE, space=event_space), "Access Manager reçoit ownership par erreur", errors)
    if event_manager and paid_event_offer is not None:
        _require(can(event_manager, PermissionCode.ACTIVITY_MANAGE, activity=paid_event_offer.activity), "Event manager sans autorité Activity", errors)
    if scanner and event_scanner_assignment is not None:
        _require(can(scanner, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=event_scanner_assignment.activity), "scanner sans autorité de contrôle Event", errors)
        _require(not can(scanner, PermissionCode.FINANCE_VIEW, space=event_scanner_assignment.activity.space), "scanner reçoit Finance par erreur", errors)
    if scanner and transport_scanner_assignment is not None:
        _require(can(scanner, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=transport_scanner_assignment.activity), "scanner sans autorité de contrôle Transport", errors)
    if activity_local and transport_space:
        local_mandate = Mandate.objects.filter(
            profile=activity_local,
            scope_type=AuthorityScope.ACTIVITY,
            activity__space=transport_space,
            role__code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            status=MandateStatus.ACTIVE,
        ).select_related("activity").first()
        _require(local_mandate is not None, "Activity-local manager sans Mandate Activity", errors)
        if local_mandate is not None:
            _require(can(activity_local, PermissionCode.ACTIVITY_MANAGE, activity=local_mandate.activity), "Activity-local manager sans gestion Activity", errors)
            other_activity = Activity.objects.filter(space=transport_space).exclude(pk=local_mandate.activity_id).first()
            _require(other_activity is not None, "seconde Activity Transport absente pour tester l’isolation", errors)
            if other_activity is not None:
                _require(not can(activity_local, PermissionCode.ACTIVITY_MANAGE, activity=other_activity), "Activity-local manager déborde sur une autre Activity", errors)
            _require(not can(activity_local, PermissionCode.SPACE_MANAGE, space=transport_space), "Activity-local manager reçoit tout l’Espace", errors)
    if team_only and event_space:
        _require(TeamMembership.objects.filter(user=team_only, team__organization=event_space, status="active").exists(), "persona Team-only sans TeamMembership", errors)
        _require(not can(team_only, PermissionCode.SPACE_VIEW, space=event_space), "TeamMembership seule donne une autorité", errors)
        _require(not Mandate.objects.filter(profile=team_only, status=MandateStatus.ACTIVE).exists(), "persona Team-only possède un Mandate inattendu", errors)
    if staff:
        _require(can(staff, PermissionCode.PLATFORM_MANAGE), "staff sans autorité plateforme", errors)
        _require(not Mandate.objects.filter(profile=staff, scope_type=AuthorityScope.SPACE, status=MandateStatus.ACTIVE).exists(), "staff dépend artificiellement de Mandates Espace", errors)

    if errors:
        raise BetaScenarioValidationError("Validation bêta échouée: " + "; ".join(errors))

    return {
        "personas": len(personas),
        "future_event_occurrences": event_occurrences.count(),
        "future_transport_occurrences": transport_occurrences.count(),
        "non_event_activities": Activity.objects.filter(pk__in=transport_activity_ids).count(),
        "non_event_occurrences": Occurrence.objects.filter(activity_id__in=transport_activity_ids).count(),
        "non_event_journeys": Journey.objects.filter(activity_id__in=transport_activity_ids).count(),
        "non_event_orders": CommerceOrder.objects.filter(journey__activity_id__in=transport_activity_ids).count(),
        "non_event_payments": Payment.objects.filter(commerce_order__journey__activity_id__in=transport_activity_ids).count(),
        "non_event_accesses": Access.objects.filter(activity_id__in=transport_activity_ids).count(),
        "non_event_access_uses": AccessUse.objects.filter(access__activity_id__in=transport_activity_ids, result=AccessUseResult.ACCEPTED).count(),
        "journeys": Journey.objects.filter(initiated_by__email__in=expected_emails).count(),
        "orders": CommerceOrder.objects.filter(source_key__startswith="beta:").count(),
        "payments": Payment.objects.filter(metadata__seed="makolo-beta").count(),
        "accesses": Access.objects.filter(source_key__startswith="beta:").count(),
        "scanner_assignments": ScannerAssignment.objects.filter(agent__email=BETA_PERSONAS["scanner"]).count(),
    }

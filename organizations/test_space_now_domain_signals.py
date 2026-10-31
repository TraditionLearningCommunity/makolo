"""Contract tests: only owner-grounded cross-domain facts enter Space Now."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from activities.models import Activity, Occurrence, OccurrenceStatus
from automation.models import (
    AutomationExecution, AutomationRule, DomainAutomationActionKind,
    DomainAutomationExecutionStatus,
)
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.models import (
    CapacityPool, CapacityReservation, CapacityReservationStatus,
)
from commerce.models import (
    CommerceOrder, CommerceOrderStatus, PaymentMode,
)
from journeys.models import Journey, JourneyStatus, WorkflowKind
from operations.models import (
    IncidentCategory, IncidentSeverity, IncidentStatus, OperationsIncident,
)
from organizations.models import Organization
from payments.models import (
    Payment, PaymentObligation, PaymentObligationProcessingMode,
    PaymentObligationReason, PaymentObligationStatus, PaymentStatus,
)


class SpaceNowDomainSignalTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="space-now-domain-owner",
            email="space-now-domain-owner@test.local",
            password="x",
        )
        self.limited = User.objects.create_user(
            username="space-now-domain-limited",
            email="space-now-domain-limited@test.local",
            password="x",
        )
        self.space = Organization.objects.create(
            name="Now owner space", slug="space-now-owners",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Atelier", slug="space-now-owner-activity",
            space=self.space, created_by=self.owner,
        )
        grant_activity_role(
            profile=self.limited, activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        self.client = APIClient()

    def _now(self, viewer=None, **query):
        self.client.force_authenticate(viewer or self.owner)
        return self.client.get(
            f"/api/v1/organizations/workspaces/{self.space.slug}/now/",
            query,
        )

    def _journey(self, *, activity=None, workflow=WorkflowKind.REGISTRATION):
        return Journey.objects.create(
            initiated_by=self.owner, beneficiary=self.owner,
            activity=activity or self.activity,
            workflow=workflow, status=JourneyStatus.SUBMITTED,
        )

    def _order(self, *, expires_at=None, payable=False):
        amount = Decimal("12.00") if payable else Decimal("0.00")
        return CommerceOrder.objects.create(
            journey=self._journey(workflow=WorkflowKind.PURCHASE),
            buyer=self.owner,
            payee_space=self.space,
            status=CommerceOrderStatus.PENDING,
            payment_mode=PaymentMode.UPFRONT if payable else PaymentMode.NONE,
            subtotal=amount, total=amount, expected_payee_amount=amount,
            expires_at=expires_at,
        )

    def test_incident_is_actionable_only_when_unresolved_high_priority_and_scoped(self):
        incident = OperationsIncident.objects.create(
            title="Un incident réel", category=IncidentCategory.ACCESS,
            severity=IncidentSeverity.HIGH, status=IncidentStatus.OPEN,
            description="Incident constaté par Operations",
            organization=self.space, activity=self.activity,
            opened_by=self.owner,
        )
        OperationsIncident.objects.create(
            title="Bruit ordinaire", category=IncidentCategory.ACCESS,
            severity=IncidentSeverity.LOW, status=IncidentStatus.OPEN,
            description="Une observation sans priorité",
            organization=self.space, activity=self.activity,
            opened_by=self.owner,
        )
        foreign_activity = Activity.objects.create(
            title="Autre activité", slug="space-now-other-activity",
            space=self.space, created_by=self.owner,
        )
        OperationsIncident.objects.create(
            title="Incident réservé", category=IncidentCategory.SECURITY,
            severity=IncidentSeverity.CRITICAL, status=IncidentStatus.OPEN,
            description="Ne jamais divulguer",
            organization=self.space, activity=foreign_activity,
            opened_by=self.owner,
        )
        limited = self._now(self.limited)
        self.assertEqual(limited.status_code, 200, limited.data)
        incidents = [
            row for row in limited.data["items"]
            if row["source"]["kind"] == "operations_incident"
        ]
        self.assertEqual(len(incidents), 1, limited.data)
        self.assertEqual(incidents[0]["source"]["id"], str(incident.pk))
        self.assertNotIn("Ne jamais divulguer", str(limited.data))
        self.assertEqual(incidents[0]["consequence"]["state"], "unknown")

        incident.status = IncidentStatus.RESOLVED
        incident.resolution = "Incident clôturé"
        incident.save()
        resolved = self._now(self.limited)
        self.assertFalse(any(
            row["source"]["id"] == str(incident.pk)
            for row in resolved.data["items"]
        ))

    def test_more_than_24_admitted_incidents_are_not_hidden(self):
        rows = [
            OperationsIncident(
                title=f"Incident non résolu {index}",
                category=IncidentCategory.ACCESS,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.OPEN,
                organization=self.space,
                activity=self.activity,
                opened_by=self.owner,
                description="Incident opérationnel confirmé.",
            )
            for index in range(27)
        ]
        OperationsIncident.objects.bulk_create(rows)
        response = self._now(self.limited)
        self.assertEqual(response.status_code, 200, response.data)
        shown = [
            row for row in response.data["items"]
            if row["source"]["kind"] == "operations_incident"
        ]
        self.assertEqual(len(shown), 27)
        self.assertFalse(response.data["has_more"])
        self.assertEqual(response.data["selection"]["state"], "partial")

    def test_access_use_refusal_is_not_an_access_state_or_a_credential(self):
        current = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=self.activity, label="En cours",
            start_at=current - timedelta(minutes=30),
            end_at=current + timedelta(minutes=30),
            status=OccurrenceStatus.SCHEDULED,
        )
        access = Access.objects.create(
            activity=self.activity, occurrence=occurrence,
            beneficiary=self.owner, status=AccessStatus.REVOKED,
        )
        denied = AccessUse.objects.create(
            access=access, occurrence=occurrence, actor=self.limited,
            result=AccessUseResult.REVOKED,
            used_at=current,
        )
        first = self._now(self.limited)
        refusals = [
            row for row in first.data["items"]
            if row["source"]["kind"] == "access_use"
        ]
        self.assertEqual(len(refusals), 1, first.data)
        self.assertEqual(refusals[0]["source"]["id"], str(denied.pk))
        self.assertEqual(refusals[0]["handoffs"][0]["target"], "space_occurrence_day_of")
        self.assertEqual(refusals[0]["handoffs"][0]["id"], str(occurrence.pk))
        self.assertNotIn("credential", str(first.data).lower())
        self.assertNotIn(self.owner.email, str(first.data))

        AccessUse.objects.create(
            access=access, occurrence=occurrence, actor=self.limited,
            result=AccessUseResult.ACCEPTED,
            used_at=current + timedelta(seconds=1),
        )
        after = self._now(self.limited)
        self.assertFalse(any(
            row["source"]["kind"] == "access_use" for row in after.data["items"]
        ))

    def test_capacity_sold_out_is_not_an_alert_but_overallocation_is(self):
        pool = CapacityPool.objects.create(
            activity=self.activity, total_quantity=2, label="Places atelier",
        )
        journey = self._journey()
        CapacityReservation.objects.create(
            pool=pool, journey=journey, quantity=2,
            status=CapacityReservationStatus.COMMITTED,
        )
        sold_out = self._now(self.limited)
        self.assertFalse(any(
            row["source"]["kind"] == "capacity_pool"
            for row in sold_out.data["items"]
        ))
        CapacityReservation.objects.create(
            pool=pool, journey=journey, quantity=1,
            status=CapacityReservationStatus.HELD,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        over = self._now(self.limited)
        anomalies = [
            row for row in over.data["items"]
            if row["source"]["kind"] == "capacity_pool"
        ]
        self.assertEqual(len(anomalies), 1, over.data)
        self.assertEqual(anomalies[0]["why_now"]["reason"], "capacity_overallocated")

    def test_commerce_requires_explicit_upcoming_expiry_not_just_pending(self):
        now = timezone.now()
        due = self._order(expires_at=now + timedelta(hours=5), payable=True)
        self._order(expires_at=now + timedelta(days=8), payable=True)
        self._order(payable=True)
        # A free pending order is not evidence that the payer must act.
        self._order(expires_at=now + timedelta(hours=2))
        result = self._now()
        commerce = [
            row for row in result.data["items"]
            if row["source"]["kind"] == "commerce_order"
        ]
        self.assertEqual(len(commerce), 1, result.data)
        self.assertEqual(commerce[0]["source"]["id"], str(due.pk))
        self.assertEqual(commerce[0]["response"]["type"], "wait")
        self.assertEqual(
            commerce[0]["handoffs"][0]["target"], "space_commerce_order",
        )
        self.assertEqual(
            commerce[0]["timing"]["deadline_at"], due.expires_at.isoformat(),
        )
        self.assertEqual(result.data["selection"]["state"], "partial")

    def test_overdue_space_debtor_obligation_is_visible_only_to_finance_authority(self):
        past = timezone.now() - timedelta(hours=3)
        obligation = PaymentObligation.objects.create(
            journey=self._journey(),
            payer_space=self.space,
            payee_platform=True,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Frais à régler pour cet Espace",
            amount=Decimal("11.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            status=PaymentObligationStatus.PENDING,
            due_at=past,
        )
        # Merely outstanding without a passed due date is not attention.
        PaymentObligation.objects.create(
            journey=self._journey(),
            payer_space=self.space, payee_platform=True,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Obligation future non urgente",
            amount=Decimal("8.00"), currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            status=PaymentObligationStatus.PENDING,
            due_at=timezone.now() + timedelta(days=8),
        )
        confirmed = PaymentObligation.objects.create(
            journey=self._journey(), payer_space=self.space, payee_platform=True,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Obligation déjà réglée",
            amount=Decimal("8.00"), currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            status=PaymentObligationStatus.SATISFIED,
            satisfied_at=timezone.now(),
            due_at=past,
        )
        response = self._now()
        self.assertEqual(response.status_code, 200, response.data)
        results = [
            row for row in response.data["items"]
            if row["source"]["kind"] == "payment_obligation"
        ]
        self.assertEqual(len(results), 1, response.data)
        self.assertEqual(results[0]["source"]["id"], str(obligation.pk))
        self.assertEqual(
            results[0]["why_now"]["reason"],
            "space_payment_obligation_overdue",
        )
        self.assertEqual(results[0]["consequence"]["state"], "unknown")
        self.assertEqual(
            results[0]["handoffs"][0]["target"], "space_payment_obligation",
        )
        self.assertNotIn(str(confirmed.pk), str(results))
        self.assertNotIn("payer_profile", str(response.data))

        path = (
            f"/api/v1/organizations/workspaces/{self.space.slug}/"
            f"payment-obligations/{obligation.pk}/"
        )
        self.client.force_authenticate(self.owner)
        read = self.client.get(path)
        self.assertEqual(read.status_code, 200, read.data)
        self.assertEqual(read.data["id"], str(obligation.pk))
        self.assertEqual(read.data["amount"], "11.00")
        self.assertEqual(read["Cache-Control"], "private, no-store")
        self.assertNotIn("payer_profile", str(read.data))
        self.client.force_login(self.owner)
        web = self.client.get(reverse(
            "organizations:space-payment-obligation",
            kwargs={"slug": self.space.slug, "obligation_id": obligation.pk},
        ))
        # Owner read is not a payment-by-proxy or an authority transfer.
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "11.00 USD")
        self.assertContains(web, "Frais à régler pour cet Espace")

        limited = self._now(self.limited)
        self.assertFalse(any(
            item["source"]["kind"] == "payment_obligation"
            for item in limited.data["items"]
        ))
        self.client.force_authenticate(self.limited)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_obligation_owner_rejects_other_space_even_for_finance_owner(self):
        outsider_space = Organization.objects.create(
            name="Espace tiers", slug="space-now-debtor-foreign",
            created_by=self.owner,
        )
        foreign_activity = Activity.objects.create(
            title="Activité tierce", slug="space-now-third-activity",
            created_by=self.owner, space=outsider_space,
        )
        foreign = PaymentObligation.objects.create(
            journey=self._journey(activity=foreign_activity),
            payer_space=outsider_space,
            payee_platform=True,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Obligation non partageable",
            amount=Decimal("3.00"),
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            status=PaymentObligationStatus.PENDING,
            due_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_authenticate(self.owner)
        url = (
            f"/api/v1/organizations/workspaces/{self.space.slug}/"
            f"payment-obligations/{foreign.pk}/"
        )
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotIn(str(foreign.pk), str(self._now().data["items"]))

    def test_recent_failed_automation_is_scoped_to_activity_manage(self):
        rule = AutomationRule.objects.create(
            name="Règle d'activité",
            space=self.space, activity=self.activity,
            trigger_event_type=DomainEventType.JOURNEY_SUBMITTED,
            action_config={
                "recipient": "beneficiary",
                "title": "Rappel de démarche",
                "message": "Un suivi est disponible.",
                "category": "system",
            },
            created_by=self.owner,
        )
        event = DomainEventOutbox.objects.create(
            event_type=DomainEventType.JOURNEY_SUBMITTED,
            source_type="journey", source_id=str(self._journey().pk),
            idempotency_key="space-now-domain-automation-event",
            space_id=self.space.pk,
            activity_id=self.activity.pk,
        )
        execution = AutomationExecution.objects.create(
            rule=rule, domain_event=event,
            action=DomainAutomationActionKind.NOTIFICATION,
            status=DomainAutomationExecutionStatus.FAILED,
        )
        response = self._now(self.limited)
        failures = [
            row for row in response.data["items"]
            if row["source"]["kind"] == "automation_execution"
        ]
        self.assertEqual(len(failures), 1, response.data)
        self.assertEqual(failures[0]["source"]["id"], str(execution.pk))
        self.assertNotIn("Rappel de démarche", str(response.data))
        execution.status = DomainAutomationExecutionStatus.COMPLETED
        execution.save()
        after = self._now(self.limited)
        self.assertFalse(any(
            row["source"]["kind"] == "automation_execution"
            for row in after.data["items"]
        ))

    def test_payment_failure_retires_after_new_attempt(self):
        order = self._order(
            payable=True, expires_at=timezone.now() + timedelta(hours=8),
        )
        failure = Payment.objects.create(
            commerce_order=order, status=PaymentStatus.FAILED,
            amount=Decimal("12.00"), currency="USD",
        )
        first = self._now()
        payments = [
            row for row in first.data["items"]
            if row["source"]["kind"] == "payment"
        ]
        self.assertEqual(len(payments), 1, first.data)
        self.assertEqual(payments[0]["source"]["id"], str(failure.pk))
        self.assertEqual(
            payments[0]["handoffs"][0]["target"], "space_commerce_order",
        )
        self.assertFalse(any(
            row["source"]["kind"] == "commerce_order"
            and row["source"]["id"] == str(order.pk)
            for row in first.data["items"]
        ))
        Payment.objects.create(
            commerce_order=order, status=PaymentStatus.PROCESSING,
            amount=Decimal("12.00"), currency="USD",
        )
        second = self._now()
        self.assertFalse(any(
            row["source"]["kind"] == "payment"
            for row in second.data["items"]
        ))
        self.assertTrue(any(
            row["source"]["kind"] == "commerce_order"
            and row["source"]["id"] == str(order.pk)
            for row in second.data["items"]
        ))

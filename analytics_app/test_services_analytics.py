from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from activities.models import Activity
from journeys.models import (
    Journey,
    JourneyBlocker,
    JourneyBlockerCategory,
    JourneyBlockerSeverity,
    JourneyBlockerStatus,
    JourneyStatus,
    JourneyStep,
    JourneyStepKind,
    JourneyStepStatus,
    WorkflowKind,
)
from organizations.models import Organization
from payments.models import (
    Payment,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
    PaymentProvider,
    PaymentStatus,
)
from services.models import ServiceCurrentOutcome, ServiceDetails, ServiceJourneyContext, ServiceKind

from .service_analytics import service_activity_summary


User = get_user_model()


class ServiceAnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "services-analytics",
            "services-analytics@example.com",
            "Analytics-2026!",
        )
        self.space = Organization.objects.create(
            name="Services analytics space",
            created_by=self.user,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.user,
            title="Accompagnement candidature",
        )
        ServiceDetails.objects.create(
            activity=self.activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
        )
        self.now = timezone.now()

    def _journey(self, *, status=JourneyStatus.DRAFT, started_at=None, fulfilled_at=None, outcome=ServiceCurrentOutcome.NOT_SUBMITTED):
        journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            status=status,
            started_at=started_at,
            fulfilled_at=fulfilled_at,
        )
        ServiceJourneyContext.objects.create(
            journey=journey,
            current_outcome=outcome,
        )
        return journey

    def test_rates_are_explicit_and_fulfillment_is_separate_from_external_success(self):
        fulfilled_unsuccessful = self._journey(
            status=JourneyStatus.FULFILLED,
            started_at=self.now - timedelta(days=4),
            fulfilled_at=self.now - timedelta(days=1),
            outcome=ServiceCurrentOutcome.UNSUCCESSFUL,
        )
        self._journey()
        self._journey(
            status=JourneyStatus.IN_PROGRESS,
            started_at=self.now - timedelta(days=2),
            outcome=ServiceCurrentOutcome.SUCCESSFUL,
        )

        JourneyStep.objects.create(
            journey=fulfilled_unsuccessful,
            kind=JourneyStepKind.DOCUMENT,
            title="Document",
            status=JourneyStepStatus.COMPLETED,
            due_at=self.now - timedelta(days=2),
            started_at=self.now - timedelta(days=3),
            completed_at=self.now - timedelta(days=1),
        )
        overdue_journey = Journey.objects.filter(activity=self.activity, started_at__isnull=True).first()
        JourneyStep.objects.create(
            journey=overdue_journey,
            kind=JourneyStepKind.ACTION,
            title="Action",
            status=JourneyStepStatus.READY,
            due_at=self.now - timedelta(hours=1),
        )
        JourneyBlocker.objects.create(
            journey=overdue_journey,
            category=JourneyBlockerCategory.MISSING_DOCUMENT,
            severity=JourneyBlockerSeverity.HIGH,
            title="Pièce manquante",
            status=JourneyBlockerStatus.ACTIVE,
        )

        summary = service_activity_summary(self.activity, now=self.now)

        self.assertEqual(summary["journeys"]["volume"], 3)
        self.assertEqual(summary["journeys"]["start_rate"]["numerator"], 2)
        self.assertEqual(summary["journeys"]["start_rate"]["denominator"], 3)
        self.assertEqual(summary["journeys"]["makolo_fulfillment_rate"]["numerator"], 1)
        self.assertEqual(summary["journeys"]["makolo_fulfillment_rate"]["denominator"], 2)
        self.assertEqual(summary["journeys"]["external_success_rate"]["numerator"], 1)
        self.assertEqual(summary["journeys"]["external_success_rate"]["denominator"], 2)
        self.assertEqual(summary["steps"]["currently_overdue"], 1)
        self.assertEqual(summary["steps"]["completed_late"], 1)
        self.assertEqual(summary["blockers"]["by_status"][JourneyBlockerStatus.ACTIVE], 1)
        self.assertNotEqual(
            summary["journeys"]["makolo_fulfillment_rate"],
            summary["journeys"]["external_success_rate"],
        )

    def test_financial_amounts_are_permission_gated_and_currencies_never_mix(self):
        provider_journey = self._journey(
            status=JourneyStatus.IN_PROGRESS,
            started_at=self.now - timedelta(days=1),
        )
        external_journey = self._journey(
            status=JourneyStatus.IN_PROGRESS,
            started_at=self.now - timedelta(hours=12),
        )
        usd = PaymentObligation.objects.create(
            journey=provider_journey,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Frais dossier",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            status=PaymentObligationStatus.PENDING,
            payee_space=self.space,
        )
        PaymentObligation.objects.create(
            journey=external_journey,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="Frais externes",
            amount=Decimal("25000.00"),
            currency="CDF",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            status=PaymentObligationStatus.PENDING,
            external_payee_name="Institution externe fictive",
        )
        Payment.objects.create(
            obligation=usd,
            initiated_by=self.user,
            provider=PaymentProvider.SANDBOX,
            status=PaymentStatus.FAILED,
            amount=Decimal("10.00"),
            currency="USD",
        )

        hidden = service_activity_summary(self.activity, include_financials=False, now=self.now)
        visible = service_activity_summary(self.activity, include_financials=True, now=self.now)

        self.assertIsNone(hidden["payments"]["financials"])
        self.assertEqual(visible["payments"]["provider_payment_failed"], 1)
        amounts = {
            row["currency"]: row["amount"]
            for row in visible["payments"]["financials"]["obligations_by_currency"]
        }
        self.assertEqual(amounts, {"CDF": Decimal("25000.00"), "USD": Decimal("10.00")})

    def test_query_count_does_not_grow_with_more_service_journeys(self):
        self._journey(status=JourneyStatus.IN_PROGRESS, started_at=self.now - timedelta(hours=1))
        with CaptureQueriesContext(connection) as baseline:
            service_activity_summary(self.activity, now=self.now)

        for index in range(5):
            self._journey(
                status=JourneyStatus.IN_PROGRESS,
                started_at=self.now - timedelta(hours=index + 2),
            )
        with CaptureQueriesContext(connection) as larger:
            service_activity_summary(self.activity, now=self.now)

        self.assertLessEqual(len(larger), len(baseline) + 1)

    def test_non_service_activity_is_rejected(self):
        other = Activity.objects.create(
            space=self.space,
            created_by=self.user,
            title="Not a Service",
        )
        with self.assertRaisesMessage(ValueError, "Service analytics require"):
            service_activity_summary(other)

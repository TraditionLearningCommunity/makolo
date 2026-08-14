from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from access.models import AccessStatus
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization
from payments.models import Payment
from commerce.models import CommerceOrder

from .access_bridge import issue_access_from_capacity
from .models import CapacityPool, CapacityReservationStatus
from .services import reserve_capacity


class FreeCapacityAccessTests(TestCase):
    def test_registration_can_consume_capacity_without_commerce_or_payment(self):
        user = get_user_model().objects.create_user(username="free-capacity", email="free-capacity@example.com", password="Capacity-2026!")
        space = Organization.objects.create(name="Free Capacity Space", created_by=user)
        activity = Activity.objects.create(space=space, created_by=user, title="Inscription gratuite")
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
        )
        journey = create_journey(
            initiated_by=user,
            beneficiary=user,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
        )
        pool = CapacityPool.objects.create(activity=activity, occurrence=occurrence, total_quantity=10)
        reservation = reserve_capacity(pool=pool, journey=journey, quantity=1, source_key="free-registration")

        access = issue_access_from_capacity(
            reservation=reservation,
            beneficiary=user,
            source_key="free-registration-access",
            valid_from=None,
            valid_until=occurrence.end_at,
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)
        self.assertEqual(access.status, AccessStatus.VALID)
        self.assertEqual(CommerceOrder.objects.filter(journey=journey).count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

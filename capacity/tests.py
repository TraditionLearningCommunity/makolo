from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .models import CapacityPool, CapacityReservationStatus
from .selectors import capacity_availability
from .services import (
    InsufficientCapacity,
    commit_capacity,
    expire_capacity,
    release_capacity,
    reserve_capacity,
)


class CapacityCoreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="capacity-user", email="capacity@example.com", password="test-pass-2026")
        self.space = Organization.objects.create(name="Capacity Space", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Formation")
        self.occurrence = Occurrence.objects.create(activity=self.activity, label="Matin", start_at=timezone.now() + timedelta(days=1), end_at=timezone.now() + timedelta(days=1, hours=2))
        self.journey = create_journey(initiated_by=self.user, beneficiary=self.user, activity=self.activity, occurrence=self.occurrence, workflow=WorkflowKind.REGISTRATION)

    def test_limited_hold_commit_release_and_availability(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=3)
        reservation = reserve_capacity(pool=pool, journey=self.journey, quantity=2, expires_at=timezone.now() + timedelta(minutes=10))
        availability = capacity_availability(pool)
        self.assertEqual((availability.held, availability.committed, availability.available), (2, 0, 1))
        reservation = commit_capacity(reservation=reservation)
        availability = capacity_availability(pool)
        self.assertEqual((availability.held, availability.committed, availability.available), (0, 2, 1))
        release_capacity(reservation=reservation, allow_committed=True)
        self.assertEqual(capacity_availability(pool).available, 3)

    def test_unlimited_pool_never_reports_sold_out(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=None)
        reserve_capacity(pool=pool, journey=self.journey, quantity=100)
        availability = capacity_availability(pool)
        self.assertTrue(availability.unlimited)
        self.assertIsNone(availability.available)
        self.assertFalse(availability.sold_out)

    def test_over_capacity_and_invalid_quantity_are_rejected(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=1)
        with self.assertRaises(ValidationError):
            reserve_capacity(pool=pool, journey=self.journey, quantity=0)
        with self.assertRaises(InsufficientCapacity):
            reserve_capacity(pool=pool, journey=self.journey, quantity=2)

    def test_scope_consistency(self):
        other_activity = Activity.objects.create(space=self.space, created_by=self.user, title="Autre")
        other_occurrence = Occurrence.objects.create(activity=other_activity, start_at=timezone.now() + timedelta(days=2))
        pool = CapacityPool(activity=self.activity, occurrence=other_occurrence, total_quantity=1)
        with self.assertRaises(ValidationError):
            pool.full_clean()

    def test_expired_hold_returns_capacity_and_transition_is_idempotent(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=1)
        reservation = reserve_capacity(pool=pool, journey=self.journey, quantity=1, expires_at=timezone.now() + timedelta(seconds=1))
        future = timezone.now() + timedelta(minutes=1)
        reservation = expire_capacity(reservation=reservation, now=future)
        self.assertEqual(reservation.status, CapacityReservationStatus.EXPIRED)
        reservation = expire_capacity(reservation=reservation, now=future)
        self.assertEqual(reservation.status, CapacityReservationStatus.EXPIRED)
        self.assertEqual(capacity_availability(pool, now=future).available, 1)

    def test_release_twice_is_idempotent(self):
        pool = CapacityPool.objects.create(activity=self.activity, occurrence=self.occurrence, total_quantity=2)
        reservation = reserve_capacity(pool=pool, journey=self.journey, quantity=1)
        release_capacity(reservation=reservation)
        second = release_capacity(reservation=reservation)
        self.assertEqual(second.status, CapacityReservationStatus.RELEASED)
        self.assertEqual(capacity_availability(pool).available, 2)

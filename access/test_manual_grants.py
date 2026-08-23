from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from capacity.services import InsufficientCapacity
from commerce.models import CommerceOrder, Offer, OfferStatus, PaymentMode
from core.models import DomainEventOutbox
from core.participant_presentation import resolve_participant_activity_state
from core.participant_selectors import participant_state_context
from domain_events.contracts import DomainEventType
from events.models import Event
from organizations.models import Organization
from payments.models import Payment
from tickets.models import Ticket, TicketOrder

from .manual_grants import grant_access_manually
from .models import Access, AccessStatus, CredentialStatus
from .services import revoke_access


User = get_user_model()


class ManualAccessGrantTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="manual-creator",
            email="manual-creator@example.com",
            password="Manual-2026!",
        )
        self.owner = User.objects.create_user(
            username="manual-owner",
            email="manual-owner@example.com",
            first_name="Naomi",
            last_name="Kabongo",
            password="Manual-2026!",
        )
        self.local_manager = User.objects.create_user(
            username="manual-local",
            email="manual-local@example.com",
            password="Manual-2026!",
        )
        self.outsider = User.objects.create_user(
            username="manual-outsider",
            email="manual-outsider@example.com",
            password="Manual-2026!",
        )
        self.beneficiary = User.objects.create_user(
            username="manual-beneficiary",
            email="manual-beneficiary@example.com",
            password="Manual-2026!",
        )
        self.second_beneficiary = User.objects.create_user(
            username="manual-second",
            email="manual-second@example.com",
            password="Manual-2026!",
        )
        self.space = Organization.objects.create(
            name="Manual Grant Space",
            created_by=self.creator,
        )
        self.other_space = Organization.objects.create(
            name="Other Grant Space",
            created_by=self.creator,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Atelier manuel",
            status=ActivityStatus.PUBLISHED,
        )
        self.other_activity = Activity.objects.create(
            space=self.other_space,
            created_by=self.creator,
            title="Autre atelier",
            status=ActivityStatus.PUBLISHED,
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=1),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        grant_activity_role(
            profile=self.local_manager,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )

    def grant(self, **overrides):
        values = {
            "actor": self.owner,
            "beneficiary": self.beneficiary,
            "activity": self.activity,
            "occurrence": self.occurrence,
        }
        values.update(overrides)
        return grant_access_manually(**values)

    def test_nominal_grant_is_valid_attributed_and_credentialed_without_commerce(self):
        access = self.grant(reason="Intervenant invité")

        self.assertEqual(access.status, AccessStatus.VALID)
        self.assertEqual(access.beneficiary, self.beneficiary)
        self.assertEqual(access.activity, self.activity)
        self.assertEqual(access.occurrence, self.occurrence)
        self.assertEqual(access.issued_by, self.owner)
        self.assertIsNone(access.journey_id)
        self.assertEqual(access.valid_from, self.occurrence.start_at)
        self.assertEqual(access.valid_until, self.occurrence.end_at)
        self.assertEqual(
            access.credentials.filter(status=CredentialStatus.ACTIVE).count(),
            1,
        )
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(TicketOrder.objects.count(), 0)
        self.assertEqual(CommerceOrder.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.ACCESS_ISSUED,
            source_id=str(access.pk),
        )
        self.assertEqual(event.payload["beneficiary_id"], str(self.beneficiary.pk))
        self.assertEqual(event.payload["issued_by_id"], str(self.owner.pk))
        self.assertEqual(event.payload["status"], AccessStatus.VALID)
        self.assertEqual(event.payload["reason"], "Intervenant invité")

    def test_occurrence_scope_and_validity_are_enforced(self):
        with self.assertRaises(ValidationError):
            self.grant(occurrence=self.other_occurrence)
        self.assertFalse(Access.objects.exists())

        cancelled = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=4),
            end_at=timezone.now() + timedelta(days=4, hours=1),
            status=OccurrenceStatus.CANCELLED,
        )
        with self.assertRaises(ValidationError):
            self.grant(occurrence=cancelled)

        past = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            self.grant(occurrence=past)

    def test_actor_must_have_activity_access_manage(self):
        with self.assertRaises(PermissionDenied):
            self.grant(actor=self.outsider)
        self.assertFalse(Access.objects.exists())

        access = self.grant(actor=self.local_manager)
        self.assertEqual(access.issued_by, self.local_manager)

        with self.assertRaises(PermissionDenied):
            grant_access_manually(
                actor=self.local_manager,
                beneficiary=self.second_beneficiary,
                activity=self.other_activity,
                occurrence=self.other_occurrence,
            )

    def test_inactive_beneficiary_and_terminal_activity_are_rejected(self):
        self.beneficiary.is_active = False
        self.beneficiary.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.grant()
        self.beneficiary.is_active = True
        self.beneficiary.save(update_fields=["is_active"])

        for status in (
            ActivityStatus.CANCELLED,
            ActivityStatus.COMPLETED,
            ActivityStatus.ARCHIVED,
        ):
            with self.subTest(status=status):
                self.activity.status = status
                self.activity.save(update_fields=["status", "updated_at"])
                with self.assertRaises(ValidationError):
                    self.grant()
        self.assertFalse(Access.objects.exists())

    def test_active_duplicate_is_refused_but_revoked_history_allows_new_grant(self):
        first = self.grant()
        with self.assertRaises(ValidationError):
            self.grant()
        self.assertEqual(Access.objects.count(), 1)

        revoke_access(access=first, actor=self.owner)
        first.refresh_from_db()
        self.assertEqual(first.status, AccessStatus.REVOKED)

        second = self.grant()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.status, AccessStatus.REVOKED)
        self.assertEqual(second.status, AccessStatus.VALID)
        self.assertEqual(Access.objects.count(), 2)

    def test_finite_admission_capacity_is_committed_without_order_or_payment(self):
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Admission générale",
            total_quantity=1,
            source_key="manual-admission",
        )

        access = self.grant()
        reservation = CapacityReservation.objects.get(pool=pool)
        self.assertEqual(reservation.status, CapacityReservationStatus.COMMITTED)
        self.assertEqual(reservation.quantity, 1)
        self.assertEqual(reservation.journey.beneficiary, self.beneficiary)
        self.assertEqual(reservation.journey.initiated_by, self.owner)
        self.assertIsNone(access.journey_id)
        self.assertEqual(CommerceOrder.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

        with self.assertRaises(InsufficientCapacity):
            self.grant(beneficiary=self.second_beneficiary)
        self.assertFalse(
            Access.objects.filter(beneficiary=self.second_beneficiary).exists()
        )
        self.assertEqual(
            CapacityReservation.objects.filter(
                pool=pool,
                status=CapacityReservationStatus.COMMITTED,
            ).count(),
            1,
        )

    def test_commercial_offer_pool_is_not_fabricated_into_manual_reservation(self):
        commercial_pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Stock commercial",
            total_quantity=1,
            source_key="manual-commercial-stock",
        )
        Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            capacity_pool=commercial_pool,
            name="Billet vendu",
            unit_price=Decimal("10.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )

        self.grant()
        self.assertFalse(
            CapacityReservation.objects.filter(pool=commercial_pool).exists()
        )

    def test_activity_wide_grant_cannot_bypass_occurrence_capacity(self):
        CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Capacité session",
            total_quantity=5,
            source_key="manual-occurrence-capacity",
        )
        with self.assertRaisesMessage(ValidationError, "Sélectionnez une session"):
            self.grant(occurrence=None)
        self.assertFalse(Access.objects.exists())

    def test_task17_resolver_recognizes_manual_access_and_revocation_without_event(self):
        self.assertFalse(Event.objects.filter(activity=self.activity).exists())
        before = resolve_participant_activity_state(
            profile=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            context=participant_state_context(self.beneficiary, [self.occurrence]),
            acquisition_label="S’inscrire",
            acquisition_url="/acquire/",
            detail_url="/detail/",
        )
        self.assertEqual(before.participant_state, "none")

        access = self.grant()
        after = resolve_participant_activity_state(
            profile=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            context=participant_state_context(self.beneficiary, [self.occurrence]),
            acquisition_label="S’inscrire",
            acquisition_url="/acquire/",
            detail_url="/detail/",
        )
        self.assertEqual(after.participant_state, "access_valid")
        self.assertEqual(after.label, "Vous avez accès")
        self.assertEqual(after.primary_action, "Voir mon accès")
        self.assertEqual(
            after.primary_url,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )

        revoke_access(access=access, actor=self.owner)
        revoked = resolve_participant_activity_state(
            profile=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            context=participant_state_context(self.beneficiary, [self.occurrence]),
            acquisition_label="S’inscrire",
            acquisition_url="/acquire/",
            detail_url="/detail/",
        )
        self.assertEqual(revoked.participant_state, "access_revoked")
        self.assertEqual(revoked.label, "Accès révoqué")

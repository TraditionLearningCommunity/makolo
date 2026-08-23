from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.manual_grants import grant_access_manually
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from capacity.models import CapacityPool
from commerce.models import CommerceOrder, Offer, OfferStatus, PaymentMode
from events.models import Event
from organizations.models import Organization
from payments.models import Payment
from tickets.models import Ticket, TicketOrder

from .search import search_occurrences


User = get_user_model()


class ManualAccessGrantDiscoveryTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="manual-discovery-creator",
            email="manual-discovery-creator@example.com",
        )
        self.manager = User.objects.create_user(
            username="manual-discovery-manager",
            email="manual-discovery-manager@example.com",
        )
        self.participant = User.objects.create_user(
            username="manual-discovery-participant",
            email="manual-discovery-participant@example.com",
            password="Manual-Discovery-2026!",
        )
        self.space = Organization.objects.create(
            name="Manual Discovery Space",
            created_by=self.creator,
        )
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Forum manuel Discovery",
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=3),
            end_at=self.now + timedelta(days=3, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.event = Event.objects.create(activity=self.activity, published_at=self.now)
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Stock commercial",
            total_quantity=20,
        )
        Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            capacity_pool=pool,
            name="Standard",
            unit_price=Decimal("15.00"),
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )
        grant_space_role(
            profile=self.manager,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )

    def item(self):
        result = search_occurrences(
            {"q": "Forum manuel Discovery"},
            profile=self.participant,
            now=self.now,
        )
        self.assertEqual(result.total, 1)
        return result.items[0]

    def test_manual_grant_immediately_replaces_purchase_cta_everywhere(self):
        before = self.item()
        self.assertEqual(before.participant.participant_state, "none")
        self.assertEqual(before.cta_label, "Acheter le billet")

        access = grant_access_manually(
            actor=self.manager,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            reason="Partenaire",
        )

        after = self.item()
        self.assertEqual(after.participant.participant_state, "access_valid")
        self.assertEqual(after.participant.label, "Vous avez accès")
        self.assertNotEqual(after.cta_label, "Acheter le billet")
        self.assertEqual(
            after.cta_url,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )

        self.client.force_login(self.participant)
        response = self.client.get(reverse("events:detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        state = response.context["participant_presentation"]
        self.assertEqual(state.participant_state, "access_valid")
        self.assertEqual(state.primary_url, after.cta_url)
        self.assertContains(response, "Vous avez accès")
        self.assertNotContains(response, "Acheter le billet")

        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(TicketOrder.objects.count(), 0)
        self.assertEqual(CommerceOrder.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

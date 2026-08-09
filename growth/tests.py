from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from automation.models import CRMWorkflowAction
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.models import TicketOrder, TicketOrderStatus, TicketType
from tickets.services import confirm_order, create_order

from .models import EventFeedback, MarketingAttributionStatus, MarketingChannel, MarketingLink, MarketingLinkVisit
from .services import activate_crm_preset, build_growth_v1_dashboard, submit_event_feedback


User = get_user_model()


class GrowthV1Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner-growth@example.com", username="owner-growth", password="pass12345")
        self.marketer = User.objects.create_user(email="marketing-growth@example.com", username="marketing-growth", password="pass12345")
        self.finance = User.objects.create_user(email="finance-growth@example.com", username="finance-growth", password="pass12345")
        self.event_manager = User.objects.create_user(email="event-growth@example.com", username="event-growth", password="pass12345")
        self.participant = User.objects.create_user(email="buyer-growth@example.com", username="buyer-growth", password="pass12345")
        self.outsider = User.objects.create_user(email="outsider-growth@example.com", username="outsider-growth", password="pass12345")
        self.organization = Organization.objects.create(name="Growth Events", created_by=self.owner)
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.marketer, OrganizationRole.MARKETING),
            (self.finance, OrganizationRole.FINANCE),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
        ]:
            OrganizationMembership.objects.create(organization=self.organization, user=user, role=role)
        now = timezone.now()
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Growth Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5, hours=2),
            published_at=now,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Paid",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=50,
        )
        self.link = MarketingLink.objects.create(
            organization=self.organization,
            event=self.event,
            name="WhatsApp launch",
            channel=MarketingChannel.WHATSAPP,
            created_by=self.marketer,
        )

    def test_public_short_link_records_minimal_visit(self):
        response = self.client.get(
            reverse("growth_public:redirect", kwargs={"code": self.link.code}),
            HTTP_REFERER="https://facebook.com/some/very/long/path?secret=no",
        )
        self.assertEqual(response.status_code, 302)
        visit = MarketingLinkVisit.objects.get(link=self.link)
        self.assertEqual(visit.referrer_domain, "facebook.com")
        self.assertEqual(visit.user, None)
        self.assertTrue(visit.session_key_hash)
        self.assertNotIn("secret", visit.referrer_domain)

    def test_session_visit_is_attached_after_login(self):
        self.client.get(reverse("growth_public:redirect", kwargs={"code": self.link.code}))
        visit = MarketingLinkVisit.objects.get(link=self.link)
        self.client.force_login(self.participant)
        self.client.get(reverse("discovery:home"))
        visit.refresh_from_db()
        self.assertEqual(visit.user, self.participant)

    def test_recent_marketing_visit_is_attributed_to_order_lifecycle(self):
        visit = MarketingLinkVisit.objects.create(link=self.link, user=self.participant)
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        attribution = order.marketing_attribution
        self.assertEqual(attribution.visit, visit)
        self.assertEqual(attribution.status, MarketingAttributionStatus.PENDING)
        self.assertEqual(attribution.revenue_amount, Decimal("25.00"))
        confirm_order(order=order, actor=self.owner)
        attribution.refresh_from_db()
        self.assertEqual(attribution.status, MarketingAttributionStatus.CONFIRMED)
        self.assertIsNotNone(attribution.confirmed_at)

    def test_cancelled_order_reverses_marketing_attribution(self):
        MarketingLinkVisit.objects.create(link=self.link, user=self.participant)
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        order.status = TicketOrderStatus.CANCELLED
        order.cancelled_at = timezone.now()
        order.save(update_fields=["status", "cancelled_at", "updated_at"])
        order.marketing_attribution.refresh_from_db()
        self.assertEqual(order.marketing_attribution.status, MarketingAttributionStatus.REVERSED)

    def _past_event_with_order(self):
        now = timezone.now()
        event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Past Growth Event",
            status=EventStatus.COMPLETED,
            visibility=EventVisibility.PUBLIC,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=1),
        )
        TicketOrder.objects.create(
            event=event,
            buyer=self.participant,
            customer_name="Buyer",
            customer_email=self.participant.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("15.00"),
            currency="USD",
            confirmed_at=now - timedelta(days=2),
        )
        return event

    def test_feedback_is_private_post_event_participant_feedback(self):
        event = self._past_event_with_order()
        feedback = submit_event_feedback(user=self.participant, event=event, rating=5, comment="Très bien")
        self.assertEqual(feedback.rating, 5)
        self.assertEqual(EventFeedback.objects.count(), 1)
        self.client.force_login(self.event_manager)
        response = self.client.get(reverse("growth:feedback-list", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Très bien")

    def test_feedback_rejects_non_participant(self):
        event = self._past_event_with_order()
        with self.assertRaises(PermissionDenied):
            submit_event_feedback(user=self.outsider, event=event, rating=5, comment="no")

    def test_finance_cannot_read_private_feedback(self):
        event = self._past_event_with_order()
        submit_event_feedback(user=self.participant, event=event, rating=4, comment="Privé")
        self.client.force_login(self.finance)
        response = self.client.get(reverse("growth:feedback-list", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 403)

    def test_marketing_can_create_link_but_finance_cannot(self):
        url = reverse("growth:link-new", kwargs={"slug": self.organization.slug})
        payload = {
            "event": str(self.event.pk),
            "name": "Instagram",
            "channel": MarketingChannel.INSTAGRAM,
            "attribution_window_days": 30,
        }
        self.client.force_login(self.marketer)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MarketingLink.objects.filter(name="Instagram").exists())
        self.client.force_login(self.finance)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_growth_dashboard_hides_financials_from_marketing(self):
        TicketOrder.objects.create(
            event=self.event,
            buyer=self.participant,
            customer_name="Buyer",
            customer_email=self.participant.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("80.00"),
            currency="USD",
            confirmed_at=timezone.now(),
        )
        marketing_payload = build_growth_v1_dashboard(self.organization, self.marketer)
        finance_payload = build_growth_v1_dashboard(self.organization, self.finance)
        self.assertFalse(marketing_payload["finance_visible"])
        self.assertEqual(marketing_payload["revenue_by_currency"], {})
        self.assertTrue(finance_payload["finance_visible"])
        self.assertEqual(finance_payload["revenue_by_currency"]["USD"], Decimal("80.00"))

    def test_crm_preset_is_idempotent_and_no_show_is_marketing_guarded(self):
        workflow, created = activate_crm_preset(
            organization=self.organization,
            actor=self.marketer,
            preset_key="no_show_reactivation",
            event=self.event,
        )
        again, created_again = activate_crm_preset(
            organization=self.organization,
            actor=self.marketer,
            preset_key="no_show_reactivation",
            event=self.event,
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(workflow.pk, again.pk)
        action = CRMWorkflowAction.objects.get(workflow=workflow)
        self.assertTrue(action.marketing_action)

    def test_growth_api_rejects_cross_organization_link(self):
        other_org = Organization.objects.create(name="Other Growth", created_by=self.owner)
        other_event = Event.objects.create(
            organizer=self.owner,
            organization=other_org,
            title="Other Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=10),
            end_at=timezone.now() + timedelta(days=10, hours=2),
        )
        self.client.force_login(self.marketer)
        response = self.client.post(
            reverse("growth_api:links"),
            data={
                "organization": str(self.organization.pk),
                "event": str(other_event.pk),
                "name": "Bad source",
                "channel": MarketingChannel.OTHER,
                "attribution_window_days": 30,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_endpoint_is_available_to_marketing(self):
        self.client.force_login(self.marketer)
        response = self.client.get(reverse("growth:link-qr", kwargs={"pk": self.link.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

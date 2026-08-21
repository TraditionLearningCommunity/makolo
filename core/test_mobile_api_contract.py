import re
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import NotificationPreference, Role, User
from events.models import (
    Event,
    EventCategory,
    EventStatus,
    EventVenue,
    EventVisibility,
    VenueKind,
)
from notifications.models import Notification
from organizations.models import (
    Organization,
    OrganizationVerificationStatus,
)
from payments.models import Payment
from promotions.models import DiscountType, Promotion, PromotionCode
from scanner.models import EventAccessGate, ScannerAssignment
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketType


PASSWORD = "Makolo!2026-StrongA7"
NEW_PASSWORD = "Makolo!2026-StrongB8"


class MobileMVPAPIContractTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()
        self.organizer = User.objects.create_user(
            email="organizer@makolo.test",
            username="organizer-mobile",
            password=PASSWORD,
            first_name="Omar",
            last_name="Organisateur",
        )
        self.organization = Organization.objects.create(
            name="Makolo Live",
            created_by=self.organizer,
            verification_status=OrganizationVerificationStatus.VERIFIED,
            public_profile=True,
            city="Lubumbashi",
            country="CD",
        )
        self.category = EventCategory.objects.create(name="Concerts")
        self.venue = EventVenue.objects.create(
            name="Grand Hall",
            kind=VenueKind.PHYSICAL,
            address="10 Avenue Makolo",
            city="Lubumbashi",
            country="CD",
            latitude=Decimal("-11.664700"),
            longitude=Decimal("27.479400"),
        )
        now = timezone.now()
        self.event = Event.objects.create(
            organizer=self.organizer,
            organization=self.organization,
            category=self.category,
            venue=self.venue,
            title="Makolo Night",
            short_description="Une soirée publique.",
            description="Description complète destinée aux participants Makolo.",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=4),
            timezone="Africa/Lubumbashi",
            capacity=200,
        )
        self.paid_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            description="Accès standard",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=100,
            min_per_order=1,
            max_per_order=5,
            is_active=True,
        )
        self.internal_type = TicketType.objects.create(
            event=self.event,
            name="Interne",
            description="Non destiné au checkout participant",
            price=Decimal("1.00"),
            currency="USD",
            quantity_total=10,
            is_active=False,
        )

        self.scanner = User.objects.create_user(
            email="scanner@makolo.test",
            username="scanner-mobile",
            password=PASSWORD,
        )
        scanner_role = Role.objects.create(
            name="Agent scanner mobile",
            code="scanner-agent",
            is_system=True,
        )
        self.scanner.roles.add(scanner_role)
        self.gate = EventAccessGate.objects.create(
            event=self.event,
            name="Entrée principale",
            created_by=self.organizer,
        )
        self.assignment = ScannerAssignment.objects.create(
            event=self.event,
            agent=self.scanner,
            assigned_by=self.organizer,
            access_gate=self.gate,
            label="Entrée principale",
            is_active=True,
        )

    def _register_and_login(self, suffix="participant", password=PASSWORD):
        email = f"{suffix}@makolo.test"
        username = f"{suffix}-{uuid.uuid4().hex[:8]}"
        client = APIClient()
        register = client.post(
            "/api/v1/accounts/auth/register/",
            {
                "email": email,
                "username": username,
                "password": password,
                "password_confirm": password,
                "first_name": "Pat",
                "last_name": "Participant",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201, register.data)
        login = client.post(
            "/api/v1/accounts/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        tokens = login.json()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return User.objects.get(email=email), client, tokens

    def _login_existing(self, email, password=PASSWORD):
        client = APIClient()
        response = client.post(
            "/api/v1/accounts/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        tokens = response.json()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client, tokens

    @staticmethod
    def _results(response):
        payload = response.json()
        return payload["results"] if isinstance(payload, dict) and "results" in payload else payload

    def _order_payload(self, ticket_type=None, *, quantity=1, key=None, promotion_code=""):
        return {
            "idempotency_key": str(key or uuid.uuid4()),
            "event_id": str(self.event.pk),
            "customer_name": "Pat Participant",
            "customer_email": "participant@makolo.test",
            "promotion_code": promotion_code,
            "items": [
                {
                    "ticket_type_id": str((ticket_type or self.paid_type).pk),
                    "quantity": quantity,
                }
            ],
        }

    def test_mobile_end_to_end_paid_order_sandbox_wallet_scanner_notifications(self):
        health = self.client.get("/api/v1/health/")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok", "api_version": "v1"})

        participant, client, _ = self._register_and_login()
        me = client.get("/api/v1/accounts/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["id"], str(participant.pk))

        discover = client.get("/api/v1/events/discover/")
        self.assertEqual(discover.status_code, 200)
        self.assertIn(str(self.event.pk), {row["id"] for row in self._results(discover)})

        detail = client.get(f"/api/v1/events/discover/{self.event.slug}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["slug"], self.event.slug)
        self.assertEqual(detail.json()["venue"]["city"], "Lubumbashi")
        self.assertTrue(detail.json()["ticket_availability"]["can_purchase"])

        ticket_types = client.get(f"/api/v1/events/{self.event.slug}/ticket-types/")
        self.assertEqual(ticket_types.status_code, 200)
        ticket_type_rows = self._results(ticket_types)
        self.assertIn(str(self.paid_type.pk), {row["id"] for row in ticket_type_rows})
        self.assertNotIn(str(self.internal_type.pk), {row["id"] for row in ticket_type_rows})

        key = uuid.uuid4()
        payload = self._order_payload(key=key)
        payload["customer_email"] = participant.email
        first = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.json()["status"], TicketOrderStatus.PENDING)
        order_id = first.json()["id"]

        replay = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(replay.json()["id"], order_id)
        self.assertEqual(TicketOrder.objects.filter(idempotency_key=key).count(), 1)

        payment_key = f"mobile-pay-{uuid.uuid4()}"
        payment_response = client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": order_id,
                "provider": "sandbox",
                "method": "card",
                "idempotency_key": payment_key,
            },
            format="json",
        )
        self.assertEqual(payment_response.status_code, 201, payment_response.data)
        payment_id = payment_response.json()["id"]

        payment_replay = client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": order_id,
                "provider": "sandbox",
                "method": "card",
                "idempotency_key": payment_key,
            },
            format="json",
        )
        self.assertEqual(payment_replay.status_code, 201, payment_replay.data)
        self.assertEqual(payment_replay.json()["id"], payment_id)
        self.assertEqual(Payment.objects.filter(idempotency_key=payment_key).count(), 1)

        with self.captureOnCommitCallbacks(execute=True):
            completed = client.post(
                f"/api/v1/payments/payments/{payment_id}/sandbox-complete/",
                {},
                format="json",
            )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(completed.json()["status"], "succeeded")
        self.assertEqual(completed.json()["order"]["status"], TicketOrderStatus.CONFIRMED)

        ticket_count = Ticket.objects.filter(order_id=order_id).count()
        completed_again = client.post(
            f"/api/v1/payments/payments/{payment_id}/sandbox-complete/",
            {},
            format="json",
        )
        self.assertEqual(completed_again.status_code, 200, completed_again.data)
        self.assertEqual(Ticket.objects.filter(order_id=order_id).count(), ticket_count)

        wallet = client.get("/api/v1/tickets/tickets/")
        self.assertEqual(wallet.status_code, 200)
        wallet_rows = self._results(wallet)
        ticket_data = next(row for row in wallet_rows if row["order_reference"] == first.json()["reference"])
        self.assertTrue(ticket_data["qr_token"])
        self.assertIn("updated_at", ticket_data)
        self.assertEqual(ticket_data["holder"]["user_id"], str(participant.pk))

        ticket_detail = client.get(f"/api/v1/tickets/tickets/{ticket_data['id']}/")
        self.assertEqual(ticket_detail.status_code, 200)
        self.assertEqual(ticket_detail.json()["qr_token"], ticket_data["qr_token"])

        scanner_client, _ = self._login_existing(self.scanner.email)
        scanner_events = scanner_client.get("/api/v1/scanner/events/")
        self.assertEqual(scanner_events.status_code, 200)
        self.assertIn(str(self.event.pk), {row["id"] for row in self._results(scanner_events)})
        assignments = scanner_client.get("/api/v1/scanner/assignments/current/")
        self.assertEqual(assignments.status_code, 200)
        assignment_rows = self._results(assignments)
        self.assertEqual(len(assignment_rows), 1)
        self.assertEqual(assignment_rows[0]["access_gate"]["id"], str(self.gate.pk))

        accepted = scanner_client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "access_gate_id": str(self.gate.pk),
                "token": ticket_data["qr_token"],
                "client_reference": f"scan-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertTrue(accepted.json()["accepted"])
        self.assertEqual(accepted.json()["result"], "accepted")
        self.assertIn("scan", accepted.json())

        duplicate = scanner_client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "access_gate_id": str(self.gate.pk),
                "token": ticket_data["qr_token"],
                "client_reference": f"scan-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.data)
        self.assertFalse(duplicate.json()["accepted"])
        self.assertEqual(duplicate.json()["result"], "duplicate")

        notifications = client.get("/api/v1/notifications/")
        self.assertEqual(notifications.status_code, 200)
        rows = self._results(notifications)
        titles = {row["title"] for row in rows}
        self.assertIn("Billet disponible", titles)
        self.assertIn("Paiement confirmé", titles)
        self.assertTrue(any(row.get("navigation") for row in rows))

        unread = client.get("/api/v1/notifications/unread-count/")
        self.assertGreaterEqual(unread.json()["unread_count"], 2)
        notification_id = rows[0]["id"]
        marked = client.post(f"/api/v1/notifications/{notification_id}/read/", {}, format="json")
        self.assertEqual(marked.status_code, 200)
        marked_all = client.post("/api/v1/notifications/read-all/", {}, format="json")
        self.assertEqual(marked_all.status_code, 200)
        self.assertEqual(client.get("/api/v1/notifications/unread-count/").json()["unread_count"], 0)

    def test_discovery_never_leaks_private_draft_or_suspended_organizer_events(self):
        now = timezone.now()
        draft = Event.objects.create(
            organizer=self.organizer,
            organization=self.organization,
            title="Brouillon secret",
            status=EventStatus.DRAFT,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=2),
        )
        private = Event.objects.create(
            organizer=self.organizer,
            organization=self.organization,
            title="Privé secret",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PRIVATE,
            start_at=now + timedelta(days=4),
            end_at=now + timedelta(days=4, hours=2),
        )
        suspended_org = Organization.objects.create(
            name="Organisation suspendue",
            created_by=self.organizer,
            verification_status=OrganizationVerificationStatus.SUSPENDED,
        )
        suspended_event = Event.objects.create(
            organizer=self.organizer,
            organization=suspended_org,
            title="Événement suspendu",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=5),
            end_at=now + timedelta(days=5, hours=2),
        )

        organizer_client, _ = self._login_existing(self.organizer.email)
        discover = organizer_client.get("/api/v1/events/discover/")
        ids = {row["id"] for row in self._results(discover)}
        self.assertIn(str(self.event.pk), ids)
        self.assertNotIn(str(draft.pk), ids)
        self.assertNotIn(str(private.pk), ids)
        self.assertNotIn(str(suspended_event.pk), ids)

        private_detail = organizer_client.get(f"/api/v1/events/discover/{private.slug}/")
        self.assertEqual(private_detail.status_code, 404)
        self.assertEqual(private_detail.json()["error"]["code"], "not_found")

    def test_discovery_filters_are_mvp_scoped_and_validated(self):
        response = self.client.get(
            "/api/v1/events/discover/",
            {
                "search": "Makolo",
                "category": self.category.slug,
                "city": "Lubumbashi",
                "date_min": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "date_max": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "ordering": "-start_at",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.event.pk), {row["id"] for row in self._results(response)})

        invalid = self.client.get(
            "/api/v1/events/discover/",
            {"date_min": "2030-02-02", "date_max": "2030-01-01"},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_error")
        self.assertIn("date_max", invalid.json()["error"]["fields"])

    def test_internal_ticket_type_is_absent_and_cannot_be_ordered(self):
        _, client, _ = self._register_and_login("internal-ticket")
        public_types = client.get(f"/api/v1/events/{self.event.slug}/ticket-types/")
        ids = {row["id"] for row in self._results(public_types)}
        self.assertNotIn(str(self.internal_type.pk), ids)

        payload = self._order_payload(self.internal_type)
        payload["customer_email"] = "internal-ticket@makolo.test"
        response = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertEqual(TicketOrder.objects.filter(idempotency_key=payload["idempotency_key"]).count(), 0)

    def test_order_idempotency_rejects_incompatible_reuse_and_stock_failure_is_normalized(self):
        participant, client, _ = self._register_and_login("idempotency")
        key = uuid.uuid4()
        payload = self._order_payload(key=key)
        payload["customer_email"] = participant.email
        first = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.data)

        incompatible = dict(payload)
        incompatible["items"] = [{"ticket_type_id": str(self.paid_type.pk), "quantity": 2}]
        conflict = client.post("/api/v1/tickets/orders/", incompatible, format="json")
        self.assertEqual(conflict.status_code, 400)
        self.assertIn("idempotency_key", conflict.json()["error"]["fields"])
        self.assertEqual(TicketOrder.objects.filter(idempotency_key=key).count(), 1)

        limited = TicketType.objects.create(
            event=self.event,
            name="Dernière place",
            price=Decimal("10.00"),
            currency="USD",
            quantity_total=1,
            max_per_order=5,
        )
        insufficient = self._order_payload(limited, quantity=2)
        insufficient["customer_email"] = participant.email
        response = client.post("/api/v1/tickets/orders/", insufficient, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertEqual(TicketOrder.objects.filter(idempotency_key=insufficient["idempotency_key"]).count(), 0)

    def test_free_order_confirms_and_returns_tickets_without_payment(self):
        participant, client, _ = self._register_and_login("free")
        free_type = TicketType.objects.create(
            event=self.event,
            name="Invitation gratuite",
            price=Decimal("0.00"),
            currency="USD",
            quantity_total=10,
        )
        payload = self._order_payload(free_type)
        payload["customer_email"] = participant.email
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertEqual(data["status"], TicketOrderStatus.CONFIRMED)
        self.assertEqual(data["total_amount"], "0.00")
        self.assertEqual(len(data["tickets"]), 1)
        self.assertTrue(data["tickets"][0]["qr_token"])
        self.assertFalse(Payment.objects.filter(order_id=data["id"]).exists())
        self.assertTrue(Notification.objects.filter(recipient=participant, title="Billet disponible").exists())

    def test_promotion_can_reduce_paid_order_to_zero_without_payment(self):
        participant, client, _ = self._register_and_login("promo-zero")
        promotion = Promotion.objects.create(
            organization=self.organization,
            event=self.event,
            name="Mobile 100",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("25.00"),
            currency="USD",
            max_redemptions_per_customer=1,
            is_active=True,
            created_by=self.organizer,
        )
        PromotionCode.objects.create(
            promotion=promotion,
            code="MOBILEZERO",
            is_active=True,
            created_by=self.organizer,
        )
        payload = self._order_payload(promotion_code="MOBILEZERO")
        payload["customer_email"] = participant.email
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertEqual(data["status"], TicketOrderStatus.CONFIRMED)
        self.assertEqual(data["subtotal_amount"], "25.00")
        self.assertEqual(data["discount_amount"], "25.00")
        self.assertEqual(data["total_amount"], "0.00")
        self.assertEqual(data["promotion_code"], "MOBILEZERO")
        self.assertEqual(len(data["tickets"]), 1)
        self.assertFalse(Payment.objects.filter(order_id=data["id"]).exists())

    def test_jwt_refresh_logout_and_password_change_invalidate_old_credentials(self):
        user, client, tokens = self._register_and_login("jwt-cycle")
        refresh = self.client.post(
            "/api/v1/accounts/auth/refresh/",
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, 200, refresh.data)
        rotated = refresh.json()
        self.assertIn("access", rotated)
        self.assertIn("refresh", rotated)

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated['access']}")
        changed = client.post(
            "/api/v1/accounts/auth/password/change/",
            {
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "new_password_confirm": NEW_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(client.get("/api/v1/accounts/auth/me/").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/v1/accounts/auth/refresh/",
                {"refresh": rotated["refresh"]},
                format="json",
            ).status_code,
            401,
        )

        relogin, new_tokens = self._login_existing(user.email, NEW_PASSWORD)
        logout = relogin.post(
            "/api/v1/accounts/auth/logout/",
            {"refresh": new_tokens["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, 200)
        rejected_refresh = self.client.post(
            "/api/v1/accounts/auth/refresh/",
            {"refresh": new_tokens["refresh"]},
            format="json",
        )
        self.assertEqual(rejected_refresh.status_code, 401)

    def test_password_forgot_is_non_enumerating_and_reset_uses_secure_token(self):
        user, _, _ = self._register_and_login("password-reset")
        known = self.client.post(
            "/api/v1/accounts/auth/password/forgot/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(known.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        unknown = self.client.post(
            "/api/v1/accounts/auth/password/forgot/",
            {"email": "nobody@makolo.test"},
            format="json",
        )
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        reset_match = re.search(
            r"https?://[^\s]+/account/password/reset/([^/\s]+)/([^/\s]+)/?",
            body,
        )
        self.assertIsNotNone(reset_match)
        uid, token = reset_match.groups()
        reset = self.client.post(
            "/api/v1/accounts/auth/password/reset/",
            {
                "uid": uid,
                "token": token,
                "new_password": NEW_PASSWORD,
                "new_password_confirm": NEW_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200, reset.data)
        old_login = self.client.post(
            "/api/v1/accounts/auth/login/",
            {"email": user.email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(old_login.status_code, 401)
        new_login = self.client.post(
            "/api/v1/accounts/auth/login/",
            {"email": user.email, "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(new_login.status_code, 200)
        reuse = self.client.post(
            "/api/v1/accounts/auth/password/reset/",
            {
                "uid": uid,
                "token": token,
                "new_password": PASSWORD,
                "new_password_confirm": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(reuse.status_code, 400)

    def test_notification_preferences_are_self_scoped_and_validated(self):
        user_a, client_a, _ = self._register_and_login("prefs-a")
        user_b, _, _ = self._register_and_login("prefs-b")
        before_b = NotificationPreference.objects.get(user=user_b).email_notifications

        current = client_a.get("/api/v1/accounts/notification-preferences/")
        self.assertEqual(current.status_code, 200)
        patched = client_a.patch(
            "/api/v1/accounts/notification-preferences/",
            {"email_notifications": False, "push_notifications": False},
            format="json",
        )
        self.assertEqual(patched.status_code, 200, patched.data)
        self.assertFalse(NotificationPreference.objects.get(user=user_a).email_notifications)
        self.assertEqual(NotificationPreference.objects.get(user=user_b).email_notifications, before_b)

        invalid = client_a.patch(
            "/api/v1/accounts/notification-preferences/",
            {"quiet_hours_enabled": True, "quiet_hours_start": None, "quiet_hours_end": None},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_error")

    def test_account_deletion_anonymizes_identity_but_preserves_financial_history(self):
        user, client, _ = self._register_and_login("delete-me")
        payload = self._order_payload()
        payload["customer_email"] = user.email
        order_response = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(order_response.status_code, 201)
        payment_response = client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": order_response.json()["id"],
                "provider": "sandbox",
                "method": "card",
                "payer_name": "Pat Participant",
                "payer_email": user.email,
                "idempotency_key": f"delete-pay-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(payment_response.status_code, 201)
        with self.captureOnCommitCallbacks(execute=True):
            complete = client.post(
                f"/api/v1/payments/payments/{payment_response.json()['id']}/sandbox-complete/",
                {},
                format="json",
            )
        self.assertEqual(complete.status_code, 200)
        payment = Payment.objects.get(pk=payment_response.json()["id"])
        original_amount = payment.amount
        original_reference = payment.reference

        deleted = client.post(
            "/api/v1/accounts/account/delete/",
            {"password": PASSWORD},
            format="json",
        )
        self.assertEqual(deleted.status_code, 200, deleted.data)
        self.assertEqual(deleted.json()["status"], "deleted")

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(user.email.endswith("@deleted.invalid"))
        self.assertTrue(user.username.startswith("deleted-"))
        order = TicketOrder.objects.get(pk=order_response.json()["id"])
        self.assertIsNone(order.buyer_id)
        self.assertEqual(order.customer_name, "Compte supprimé")
        ticket = Ticket.objects.get(order=order)
        self.assertIsNone(ticket.owner_id)
        self.assertEqual(ticket.holder_name, "Compte supprimé")
        payment.refresh_from_db()
        self.assertEqual(payment.amount, original_amount)
        self.assertEqual(payment.reference, original_reference)
        self.assertIsNone(payment.initiated_by_id)
        self.assertTrue(payment.payer_email.endswith("@deleted.invalid"))
        self.assertFalse(Notification.objects.filter(recipient=user).exists())
        self.assertEqual(client.get("/api/v1/accounts/auth/me/").status_code, 401)

    def test_normal_participant_has_no_scanner_surface_or_scan_permission(self):
        _, client, _ = self._register_and_login("not-scanner")
        events = client.get("/api/v1/scanner/events/")
        self.assertEqual(events.status_code, 200)
        self.assertEqual(len(self._results(events)), 0)
        assignments = client.get("/api/v1/scanner/assignments/current/")
        self.assertEqual(assignments.status_code, 200)
        self.assertEqual(len(self._results(assignments)), 0)
        denied = client.post(
            "/api/v1/scanner/scan/",
            {"event_id": str(self.event.pk), "token": "invalid"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["error"]["code"], "permission_denied")

    def test_authorized_scanner_rejects_invalid_token_wrong_event_and_wrong_gate(self):
        scanner_client, _ = self._login_existing(self.scanner.email)
        invalid = scanner_client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "access_gate_id": str(self.gate.pk),
                "token": "not-a-signed-ticket",
                "client_reference": f"invalid-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(invalid.json()["accepted"])
        self.assertEqual(invalid.json()["result"], "invalid_token")

        participant, participant_client, _ = self._register_and_login("wrong-event-ticket")
        free_type = TicketType.objects.create(
            event=self.event,
            name="Scanner fixture",
            price=Decimal("0.00"),
            quantity_total=5,
        )
        payload = self._order_payload(free_type)
        payload["customer_email"] = participant.email
        with self.captureOnCommitCallbacks(execute=True):
            order = participant_client.post("/api/v1/tickets/orders/", payload, format="json")
        token = order.json()["tickets"][0]["qr_token"]

        now = timezone.now()
        other_event = Event.objects.create(
            organizer=self.organizer,
            organization=self.organization,
            title="Autre événement scanner",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=3),
        )
        other_gate = EventAccessGate.objects.create(
            event=other_event,
            name="Autre entrée",
            created_by=self.organizer,
        )
        ScannerAssignment.objects.create(
            event=other_event,
            agent=self.scanner,
            assigned_by=self.organizer,
            access_gate=other_gate,
        )
        wrong_event = scanner_client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(other_event.pk),
                "access_gate_id": str(other_gate.pk),
                "token": token,
                "client_reference": f"wrong-event-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(wrong_event.status_code, 200)
        self.assertFalse(wrong_event.json()["accepted"])
        self.assertEqual(wrong_event.json()["result"], "wrong_event")

        unauthorized_gate = EventAccessGate.objects.create(
            event=self.event,
            name="VIP",
            created_by=self.organizer,
        )
        wrong_gate = scanner_client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "access_gate_id": str(unauthorized_gate.pk),
                "token": token,
                "client_reference": f"wrong-gate-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(wrong_gate.status_code, 403)
        self.assertEqual(wrong_gate.json()["error"]["code"], "permission_denied")

    def test_payment_participant_configuration_hides_manual_and_expiry_is_enforced(self):
        participant, client, _ = self._register_and_login("payment-edges")
        configuration = client.get("/api/v1/payments/configuration/")
        self.assertEqual(configuration.status_code, 200)
        providers = {row["value"] for row in configuration.json()["providers"]}
        self.assertIn("sandbox", providers)
        self.assertNotIn("manual", providers)

        payload = self._order_payload()
        payload["customer_email"] = participant.email
        order = client.post("/api/v1/tickets/orders/", payload, format="json")
        self.assertEqual(order.status_code, 201)
        manual = client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": order.json()["id"],
                "provider": "manual",
                "method": "cash",
                "idempotency_key": f"manual-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(manual.status_code, 403)

        expired_order = TicketOrder.objects.get(pk=order.json()["id"])
        expired_order.expires_at = timezone.now() - timedelta(seconds=1)
        expired_order.save(update_fields=["expires_at", "updated_at"])
        expired_payment = client.post(
            "/api/v1/payments/payments/",
            {
                "order_id": order.json()["id"],
                "provider": "sandbox",
                "method": "card",
                "idempotency_key": f"expired-{uuid.uuid4()}",
            },
            format="json",
        )
        self.assertEqual(expired_payment.status_code, 400)
        self.assertEqual(expired_payment.json()["error"]["code"], "validation_error")

    def test_profile_patch_accepts_json_for_native_mobile_client(self):
        _, client, _ = self._register_and_login("profile-json")
        response = client.patch(
            "/api/v1/accounts/auth/profile/update/",
            {"first_name": "Amina", "language": "fr", "timezone": "Africa/Lubumbashi"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.json()["user"]["first_name"], "Amina")

    def test_global_error_envelope_covers_authentication_validation_and_not_found(self):
        unauthenticated = self.client.get("/api/v1/notifications/")
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()["error"]["code"], "authentication_required")
        self.assertIn("fields", unauthenticated.json()["error"])

        missing = self.client.get("/api/v1/events/discover/does-not-exist/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")

        invalid = self.client.post(
            "/api/v1/accounts/auth/register/",
            {"email": "not-an-email"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_error")
        self.assertTrue(invalid.json()["error"]["fields"])

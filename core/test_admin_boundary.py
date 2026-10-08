"""Regression tests for the technical Django Admin boundary."""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase

from core.admin import DomainEventConsumptionAdmin, DomainEventOutboxAdmin
from core.models import DomainEventConsumption, DomainEventOutbox, DomainEventStatus
from domain_events.services import requeue_failed_domain_event
from operations.models import OperationsAuditLog
from trust.admin import TrustEvidenceAdmin
from trust.models import TrustEvidence


class TechnicalAdminBoundaryTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="admin-boundary-staff", is_staff=True
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="admin-boundary-tech", email="admin-tech@example.test", password="irrelevant-test-password"
        )
        self.factory = RequestFactory()

    def request_as(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def test_read_only_domain_event_tables_forbid_generic_changes(self):
        for model, model_admin in (
            (DomainEventOutbox, DomainEventOutboxAdmin),
            (DomainEventConsumption, DomainEventConsumptionAdmin),
        ):
            instance = model_admin(model, AdminSite())
            request = self.request_as(self.superuser)
            self.assertFalse(instance.has_add_permission(request))
            self.assertFalse(instance.has_change_permission(request))
            self.assertFalse(instance.has_delete_permission(request))

    def test_retry_action_only_available_to_technical_superuser(self):
        model_admin = DomainEventOutboxAdmin(DomainEventOutbox, AdminSite())
        self.assertNotIn("requeue_failed_events", model_admin.get_actions(self.request_as(self.staff)))
        self.assertIn("requeue_failed_events", model_admin.get_actions(self.request_as(self.superuser)))

    def test_retry_must_keep_attempts_and_error_evidence(self):
        event = DomainEventOutbox.objects.create(
            event_type="request.created",
            source_type="request",
            idempotency_key="admin-boundary-retry-event",
            status=DomainEventStatus.FAILED,
            attempts=1,
            max_attempts=3,
            last_error="synthetic failure",
        )
        with self.assertRaises(PermissionDenied):
            requeue_failed_domain_event(event_id=event.pk, actor=self.staff, reason="Incident recovery")
        with self.assertRaises(ValidationError):
            requeue_failed_domain_event(event_id=event.pk, actor=self.superuser, reason="x")
        requeue_failed_domain_event(event_id=event.pk, actor=self.superuser, reason="Incident recovery")
        event.refresh_from_db()
        self.assertEqual(event.status, DomainEventStatus.PENDING)
        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.last_error, "synthetic failure")
        self.assertTrue(OperationsAuditLog.objects.filter(
            action="domain_event.requeued", target_id=str(event.pk),
        ).exists())
        with self.assertRaises(ValidationError):
            requeue_failed_domain_event(event_id=event.pk, actor=self.superuser, reason="Repeat operation")

    def test_exhausted_retry_budget_does_not_get_reset(self):
        event = DomainEventOutbox.objects.create(
            event_type="request.created", source_type="request",
            idempotency_key="admin-boundary-exhausted",
            status=DomainEventStatus.FAILED, attempts=3, max_attempts=3,
        )
        with self.assertRaises(ValidationError):
            requeue_failed_domain_event(event_id=event.pk, actor=self.superuser, reason="Investigate exhausted retry")
        event.refresh_from_db()
        self.assertEqual(event.status, DomainEventStatus.FAILED)
        self.assertEqual(event.attempts, 3)

    def test_private_trust_evidence_not_visible_to_ordinary_staff(self):
        model_admin = TrustEvidenceAdmin(TrustEvidence, AdminSite())
        self.assertFalse(model_admin.has_view_permission(self.request_as(self.staff)))
        self.assertTrue(model_admin.has_view_permission(self.request_as(self.superuser)))
        self.assertIn("file", model_admin.get_exclude(self.request_as(self.superuser)))
        self.assertFalse(model_admin.has_add_permission(self.request_as(self.superuser)))
        self.assertFalse(model_admin.has_delete_permission(self.request_as(self.superuser)))

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


class CanonicalAdminMatrixTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory
        self.staff = get_user_model().objects.create_user(
            username="matrix-staff", is_staff=True,
        )
        self.tech = get_user_model().objects.create_superuser(
            username="matrix-superuser",
            email="matrix-superuser@example.test", password="technical-only-test-password",
        )
        self.factory = RequestFactory()

    def request(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def test_owner_managed_models_have_no_raw_admin_writes(self):
        from django.contrib import admin
        from accounts.models import NotificationPreference, UserDevice, UserProfile, UserSession
        from opportunities.models import (
            Opportunity, OpportunityRequirement, OpportunityRevision, OpportunitySave,
            OpportunitySource, OpportunitySourceCheck, OpportunitySubmission, OpportunityZone,
        )
        from operations.models import ModerationCase, OperationsIncident
        from organizations.models import (
            Organization, OrganizationFollow, OrganizationMembership, Team, TeamMembership,
        )
        models = (
            Organization, Team, TeamMembership, OrganizationMembership, OrganizationFollow,
            OperationsIncident, ModerationCase, Opportunity, OpportunityRevision,
            OpportunitySource, OpportunitySourceCheck, OpportunityRequirement,
            OpportunityZone, OpportunitySave, OpportunitySubmission,
            UserProfile, UserDevice, UserSession, NotificationPreference,
        )
        request = self.request(self.tech)
        for model in models:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))

    def test_account_technical_gate_and_sanitized_sessions(self):
        from django.contrib import admin
        from accounts.models import User, UserSession
        admin_user = admin.site._registry[User]
        self.assertFalse(admin_user.has_view_permission(self.request(self.staff)))
        self.assertFalse(admin_user.has_change_permission(self.request(self.staff)))
        self.assertFalse(admin_user.has_delete_permission(self.request(self.tech)))
        self.assertTrue(admin_user.has_change_permission(self.request(self.tech)))
        self.assertEqual(admin_user.get_actions(self.request(self.tech)), {})
        self.assertIn("email_verified", admin_user.get_readonly_fields(self.request(self.tech)))
        session_admin = admin.site._registry[UserSession]
        self.assertNotIn("session_key", session_admin.get_fields(self.request(self.tech)))

    def test_activity_lifecycle_and_ownership_are_not_raw_editable(self):
        from django.contrib import admin
        from activities.models import Activity, Occurrence
        admin_activity = admin.site._registry[Activity]
        admin_occurrence = admin.site._registry[Occurrence]
        request = self.request(self.tech)
        self.assertFalse(admin_activity.has_delete_permission(request))
        self.assertFalse(admin_occurrence.has_delete_permission(request))
        self.assertTrue({"status", "visibility"}.issubset(set(admin_activity.get_readonly_fields(request))))
        self.assertTrue({"status", "schedule"}.issubset(set(admin_occurrence.get_readonly_fields(request))))

    def test_recognition_uses_explicit_owner_confirmation_not_implicit_bulk_write(self):
        from django.contrib import admin
        from django.template.response import TemplateResponse
        from recognition.models import RecognitionPolicy, PolicyStatus
        policy = RecognitionPolicy.objects.create(code="admin-confirm", version=1, name="Confirm")
        request = self.factory.post("/admin/recognition/recognitionpolicy/", {
            "action": "simulate_last_30_days", "_selected_action": str(policy.pk),
        })
        request.user = self.tech
        policy_admin = admin.site._registry[RecognitionPolicy]
        response = policy_admin.simulate_last_30_days(
            request, RecognitionPolicy.objects.filter(pk=policy.pk),
        )
        self.assertIsInstance(response, TemplateResponse)
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyStatus.DRAFT)

    def test_recognition_owner_service_requires_reason_and_audits(self):
        from unittest.mock import patch
        from recognition.governance_services import record_policy_simulation, publish_policy_for_actor
        from recognition.models import RecognitionPolicy, PolicyStatus
        policy = RecognitionPolicy.objects.create(code="admin-owner", version=1, name="Owner")
        with self.assertRaises(PermissionDenied):
            record_policy_simulation(
                actor=self.staff, policy_id=policy.pk,
                expected_status=PolicyStatus.DRAFT, reason="Test simulation",
            )
        with self.assertRaises(ValidationError):
            record_policy_simulation(
                actor=self.tech, policy_id=policy.pk,
                expected_status=PolicyStatus.DRAFT, reason="",
            )
        with patch("recognition.governance_services.simulate_policy", return_value={
            "signals": 0, "matches": 0, "projected_credits": 0,
        }):
            record_policy_simulation(
                actor=self.tech, policy_id=policy.pk,
                expected_status=PolicyStatus.DRAFT,
                reason="Controlled technical simulation",
            )
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyStatus.SIMULATED)
        self.assertTrue(OperationsAuditLog.objects.filter(
            target_id=str(policy.pk), action="recognition.policy_simulated",
        ).exists())
        publish_policy_for_actor(
            actor=self.tech, policy_id=policy.pk,
            expected_status=PolicyStatus.SIMULATED,
            reason="Controlled technical publication",
        )
        self.assertTrue(OperationsAuditLog.objects.filter(
            target_id=str(policy.pk),
            action__in=("recognition.policy_published", "recognition.policy_scheduled"),
        ).exists())
        with self.assertRaises(ValidationError):
            publish_policy_for_actor(
                actor=self.tech, policy_id=policy.pk,
                expected_status=PolicyStatus.SIMULATED,
                reason="Repeat publication blocked",
            )


class TechnicalDomainHardeningTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.technical = get_user_model().objects.create_superuser(
            username="technical-domain-matrix", email="domain-matrix@example.test",
            password="technical-test-password",
        )
        self.staff = get_user_model().objects.create_user(
            username="technical-domain-staff", is_staff=True,
        )
        self.factory = RequestFactory()

    def as_user(self, user):
        request = self.factory.get("/admin/")
        request.user = user
        return request

    def test_sensitive_domain_owner_flows_are_not_generic_admin_mutations(self):
        from django.contrib import admin
        from activities.models import Activity, Occurrence, OccurrencePlace
        from events.models import Event
        from capacity.models import CapacityPool
        from commerce.models import Offer
        from tickets.models import Ticket, TicketType, TicketOrder, TicketWaitlistEntry, TicketTransfer
        from journeys.models import Journey, JourneyRequest, JourneyTransition, JourneyStep, JourneyAssignment, JourneyArtifact
        from scanner.models import ScannerAssignment, ScanLog
        from sharing.models import ShareLink, ShareEnvelope
        models = (
            Activity, Occurrence, OccurrencePlace, Event, CapacityPool, Offer,
            Ticket, TicketType, TicketOrder, TicketWaitlistEntry, TicketTransfer,
            Journey, JourneyRequest, JourneyTransition, JourneyStep, JourneyAssignment,
            JourneyArtifact, ScannerAssignment, ScanLog, ShareLink, ShareEnvelope,
        )
        request = self.as_user(self.technical)
        for model in models:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))

    def test_private_artifact_is_hidden_and_not_staff_browseable(self):
        from django.contrib import admin
        from journeys.models import JourneyArtifact, JourneyNote
        from sharing.models import ShareEnvelope
        for model in (JourneyArtifact, JourneyNote, ShareEnvelope):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_view_permission(self.as_user(self.staff)))
                self.assertTrue(model_admin.has_view_permission(self.as_user(self.technical)))
        artifact_admin = admin.site._registry[JourneyArtifact]
        self.assertNotIn("file", artifact_admin.get_fields(self.as_user(self.technical)))

    def test_provider_configuration_requires_technical_superuser(self):
        from django.contrib import admin
        from intelligence.models import ProviderConnection, IntelligenceRoute
        for model in (ProviderConnection, IntelligenceRoute):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_view_permission(self.as_user(self.staff)))
                self.assertFalse(model_admin.has_change_permission(self.as_user(self.staff)))
                self.assertTrue(model_admin.has_change_permission(self.as_user(self.technical)))
                self.assertFalse(model_admin.has_delete_permission(self.as_user(self.technical)))


    def test_allauth_framework_credentials_are_not_rendered_as_plaintext(self):
        from django import forms
        from django.contrib import admin
        from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
        app_admin = admin.site._registry[SocialApp]
        token_admin = admin.site._registry[SocialToken]
        account_admin = admin.site._registry[SocialAccount]
        self.assertFalse(app_admin.has_view_permission(self.as_user(self.staff)))
        self.assertTrue(app_admin.has_change_permission(self.as_user(self.technical)))
        self.assertFalse(app_admin.has_delete_permission(self.as_user(self.technical)))
        self.assertFalse(token_admin.has_view_permission(self.as_user(self.staff)))
        self.assertFalse(token_admin.has_change_permission(self.as_user(self.technical)))
        self.assertFalse(account_admin.has_change_permission(self.as_user(self.technical)))
        self.assertNotIn("truncated_token", token_admin.list_display)
        self.assertFalse({"token", "token_secret"} & set(token_admin.get_fields(self.as_user(self.technical))))

        form = app_admin.form(instance=SocialApp(
            provider="google", name="Technical OAuth", client_id="placeholder",
            secret="never-render-the-existing-secret", key="never-render-existing-key",
            settings={"opaque": "private-config"},
        ))
        self.assertNotIn("secret", form.fields)
        self.assertNotIn("key", form.fields)
        self.assertNotIn("settings", form.fields)
        self.assertIsInstance(form.fields["new_secret"].widget, forms.PasswordInput)
        self.assertIsInstance(form.fields["new_key"].widget, forms.PasswordInput)
        self.assertIsNone(form.fields["new_secret"].initial)
        self.assertIsNone(form.fields["settings_payload"].initial)

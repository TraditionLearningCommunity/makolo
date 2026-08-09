from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from crm.models import (
    AudienceKind,
    CampaignTemplate,
    CommunicationKind,
    CRMContact,
    CRMContactTag,
    CRMTag,
    MarketingConsent,
)
from crm.services import create_segment
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationFollow, OrganizationMembership, OrganizationRole
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus, TicketType

from .crm_runtime import process_due_crm_workflows
from .crm_services import emit_follow_trigger, emit_order_trigger
from .models import (
    CRMWorkflow,
    CRMWorkflowAction,
    CRMWorkflowActionKind,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
    CRMWorkflowRun,
    CRMWorkflowRunStatus,
    CRMWorkflowTrigger,
)


User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="Makolo <noreply@makolo.test>")
class CRMAutomationEngineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="auto-owner", email="owner@automation.test", password="Strong-password-2026!")
        self.marketing = User.objects.create_user(username="auto-marketing", email="marketing@automation.test", password="Strong-password-2026!")
        self.finance = User.objects.create_user(username="auto-finance", email="finance@automation.test", password="Strong-password-2026!")
        self.customer = User.objects.create_user(
            username="auto-customer",
            email="customer@automation.test",
            password="Strong-password-2026!",
            first_name="Grâce",
            birth_date=timezone.localdate(),
        )
        self.organization = Organization.objects.create(name="Automation Events", created_by=self.owner, public_profile=True)
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationRole.OWNER)
        OrganizationMembership.objects.create(organization=self.organization, user=self.marketing, role=OrganizationRole.MARKETING)
        OrganizationMembership.objects.create(organization=self.organization, user=self.finance, role=OrganizationRole.FINANCE)
        self.now = timezone.now().replace(microsecond=0)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Automation Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=3),
            end_at=self.now + timedelta(days=3, hours=5),
            published_at=self.now,
            capacity=100,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("30.00"),
            currency="USD",
            quantity_total=100,
        )
        self.contact = CRMContact.objects.create(
            organization=self.organization,
            user=self.customer,
            email=self.customer.email,
            name=self.customer.full_name,
            marketing_consent=MarketingConsent.SUBSCRIBED,
            consent_source="test",
            consent_updated_at=self.now,
        )
        self.template = CampaignTemplate.objects.create(
            organization=self.organization,
            name="Bienvenue",
            kind=CommunicationKind.MARKETING,
            subject="Bienvenue {{ contact.name }}",
            body="Merci de suivre {{ organization.name }}.",
            created_by=self.marketing,
        )
        self.tag = CRMTag.objects.create(organization=self.organization, name="Automatisé", created_by=self.marketing)

    def workflow(self, *, name="Workflow", trigger=CRMWorkflowTrigger.FOLLOWED_ORGANIZER, **kwargs):
        workflow = CRMWorkflow(
            organization=self.organization,
            name=name,
            trigger=trigger,
            created_by=self.marketing,
            **kwargs,
        )
        workflow.full_clean()
        workflow.save()
        return workflow

    def action(self, workflow, *, position=1, kind=CRMWorkflowActionKind.ADD_TAG, **kwargs):
        action = CRMWorkflowAction(workflow=workflow, position=position, kind=kind, **kwargs)
        action.full_clean()
        action.save()
        return action

    def order(self, *, amount=Decimal("30.00"), status=TicketOrderStatus.CONFIRMED, email=None):
        return TicketOrder.objects.create(
            event=self.event,
            buyer=self.customer,
            customer_name=self.customer.full_name,
            customer_email=email or self.customer.email,
            status=status,
            total_amount=amount,
            currency="USD",
            confirmed_at=self.now if status == TicketOrderStatus.CONFIRMED else None,
        )

    def ticket(self, order, *, status=TicketStatus.VALID, email=None):
        return Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=order,
            owner=self.customer,
            holder_name=self.customer.full_name,
            holder_email=email or self.customer.email,
            status=status,
            used_at=self.now if status == TicketStatus.USED else None,
        )

    def test_follow_trigger_is_idempotent_and_schedules_first_action(self):
        workflow = self.workflow()
        self.action(workflow, tag=self.tag, delay_minutes=30)
        follow = OrganizationFollow.objects.create(organization=self.organization, user=self.customer)

        self.assertEqual(emit_follow_trigger(follow.pk), 1)
        self.assertEqual(emit_follow_trigger(follow.pk), 0)
        run = CRMWorkflowRun.objects.get(workflow=workflow)
        action_run = run.action_runs.get()
        self.assertEqual(run.status, CRMWorkflowRunStatus.WAITING)
        self.assertGreaterEqual(action_run.scheduled_for, run.created_at + timedelta(minutes=29))

    def test_follow_signal_triggers_workflow_after_commit(self):
        workflow = self.workflow(name="Signal follower")
        self.action(workflow, tag=self.tag)
        with self.captureOnCommitCallbacks(execute=True):
            OrganizationFollow.objects.create(organization=self.organization, user=self.customer)
        self.assertTrue(CRMWorkflowRun.objects.filter(workflow=workflow, contact=self.contact).exists())

    def test_order_conditions_create_or_skip_runs(self):
        matching = self.workflow(
            name="VIP purchase",
            trigger=CRMWorkflowTrigger.ORDER_CONFIRMED,
            event=self.event,
            min_order_amount=Decimal("20.00"),
            currency="USD",
        )
        self.action(matching, tag=self.tag)
        too_high = self.workflow(
            name="Whale purchase",
            trigger=CRMWorkflowTrigger.ORDER_CONFIRMED,
            event=self.event,
            min_order_amount=Decimal("100.00"),
            currency="USD",
        )
        self.action(too_high, tag=self.tag)
        order = self.order(amount=Decimal("30.00"))

        emit_order_trigger(order.pk, CRMWorkflowTrigger.ORDER_CONFIRMED)
        self.assertEqual(CRMWorkflowRun.objects.get(workflow=matching).status, CRMWorkflowRunStatus.WAITING)
        skipped = CRMWorkflowRun.objects.get(workflow=too_high)
        self.assertEqual(skipped.status, CRMWorkflowRunStatus.SKIPPED)
        self.assertIn("montant", skipped.skip_reason.lower())

    def test_multistep_actions_run_sequentially_with_delay(self):
        workflow = self.workflow(name="Purchase journey", trigger=CRMWorkflowTrigger.ORDER_CONFIRMED, event=self.event)
        self.action(workflow, position=1, kind=CRMWorkflowActionKind.ADD_TAG, tag=self.tag)
        self.action(workflow, position=2, kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION, delay_minutes=60, title="Merci {{ contact.name }}", message="Commande {{ order.reference }} confirmée")
        order = self.order()
        emit_order_trigger(order.pk, CRMWorkflowTrigger.ORDER_CONFIRMED)

        first_stats = process_due_crm_workflows(now=timezone.now() + timedelta(seconds=2))
        self.assertEqual(first_stats["completed"], 1)
        self.assertTrue(CRMContactTag.objects.filter(contact=self.contact, tag=self.tag).exists())
        run = CRMWorkflowRun.objects.get(workflow=workflow)
        second = run.action_runs.get(action__position=2)
        self.assertEqual(second.status, CRMWorkflowActionRunStatus.QUEUED)

        early_stats = process_due_crm_workflows(now=second.scheduled_for - timedelta(seconds=1))
        self.assertEqual(early_stats["completed"], 0)
        late_stats = process_due_crm_workflows(now=second.scheduled_for + timedelta(seconds=1))
        self.assertEqual(late_stats["completed"], 1)
        run.refresh_from_db()
        self.assertEqual(run.status, CRMWorkflowRunStatus.COMPLETED)
        self.assertTrue(self.customer.makolo_notifications.filter(title__contains="Merci").exists())

    def test_marketing_email_requires_consent_and_preferences(self):
        workflow = self.workflow(name="Marketing welcome")
        self.action(workflow, kind=CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE, template=self.template)
        follow = OrganizationFollow.objects.create(
            organization=self.organization,
            user=self.customer,
            notify_announcements=True,
            email_announcements=False,
        )
        NotificationPreference.objects.create(user=self.customer, email_notifications=True, marketing_notifications=True)
        emit_follow_trigger(follow.pk)
        process_due_crm_workflows(now=timezone.now() + timedelta(seconds=1))
        self.assertEqual(len(mail.outbox), 0)
        action_run = CRMWorkflowActionRun.objects.get(run__workflow=workflow)
        self.assertEqual(action_run.status, CRMWorkflowActionRunStatus.SKIPPED)

    def test_marketing_email_sends_after_explicit_opt_in_and_renders_variables(self):
        workflow = self.workflow(name="Welcome email")
        self.action(workflow, kind=CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE, template=self.template)
        follow = OrganizationFollow.objects.create(
            organization=self.organization,
            user=self.customer,
            notify_announcements=True,
            email_announcements=True,
        )
        NotificationPreference.objects.create(user=self.customer, email_notifications=True, marketing_notifications=True)
        emit_follow_trigger(follow.pk)
        process_due_crm_workflows(now=timezone.now() + timedelta(seconds=1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Grâce", mail.outbox[0].subject)
        self.assertIn("Automation Events", mail.outbox[0].body)
        self.assertIn("Se désabonner", mail.outbox[0].body)

    def test_marketing_in_app_notification_respects_local_consent(self):
        self.contact.marketing_consent = MarketingConsent.UNSUBSCRIBED
        self.contact.save(update_fields=["marketing_consent", "updated_at"])
        workflow = self.workflow(name="Promo in app")
        self.action(
            workflow,
            kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION,
            title="Offre",
            message="Promotion",
            marketing_action=True,
        )
        follow = OrganizationFollow.objects.create(organization=self.organization, user=self.customer, notify_announcements=True)
        emit_follow_trigger(follow.pk)
        process_due_crm_workflows(now=timezone.now() + timedelta(seconds=1))
        self.assertFalse(self.customer.makolo_notifications.filter(title="Offre").exists())
        self.assertEqual(CRMWorkflowActionRun.objects.get(run__workflow=workflow).status, CRMWorkflowActionRunStatus.SKIPPED)

    def test_paused_workflow_keeps_queued_actions_suspended(self):
        workflow = self.workflow(name="Paused")
        self.action(workflow, tag=self.tag)
        follow = OrganizationFollow.objects.create(organization=self.organization, user=self.customer)
        emit_follow_trigger(follow.pk)
        workflow.is_active = False
        workflow.save(update_fields=["is_active", "updated_at"])
        process_due_crm_workflows(now=timezone.now() + timedelta(minutes=1))
        self.assertEqual(CRMWorkflowActionRun.objects.get(run__workflow=workflow).status, CRMWorkflowActionRunStatus.QUEUED)

    def test_disabled_action_is_skipped_and_chain_continues(self):
        workflow = self.workflow(name="Disabled action")
        first = self.action(workflow, position=1, tag=self.tag)
        self.action(workflow, position=2, kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION, title="Suite", message="Toujours exécutée")
        follow = OrganizationFollow.objects.create(organization=self.organization, user=self.customer)
        emit_follow_trigger(follow.pk)
        first.is_active = False
        first.save(update_fields=["is_active", "updated_at"])
        process_due_crm_workflows(now=timezone.now() + timedelta(seconds=1))
        first_run = CRMWorkflowActionRun.objects.get(run__workflow=workflow, action=first)
        self.assertEqual(first_run.status, CRMWorkflowActionRunStatus.SKIPPED)
        process_due_crm_workflows(now=timezone.now() + timedelta(seconds=2))
        self.assertTrue(self.customer.makolo_notifications.filter(title="Suite").exists())

    def test_before_event_workflows_do_not_trigger_each_other_early(self):
        order = self.order()
        self.ticket(order)
        due = self.workflow(
            name="J-3",
            trigger=CRMWorkflowTrigger.BEFORE_EVENT,
            event=self.event,
            event_offset_minutes=3 * 24 * 60,
            trigger_grace_minutes=120,
        )
        later = self.workflow(
            name="H-24",
            trigger=CRMWorkflowTrigger.BEFORE_EVENT,
            event=self.event,
            event_offset_minutes=24 * 60,
            trigger_grace_minutes=120,
        )
        self.action(due, tag=self.tag)
        self.action(later, kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION, title="H-24", message="Encore un jour")
        process_due_crm_workflows(now=self.now + timedelta(minutes=1))
        self.assertTrue(CRMWorkflowRun.objects.filter(workflow=due).exists())
        self.assertFalse(CRMWorkflowRun.objects.filter(workflow=later).exists())

    def test_no_show_targets_only_ticket_holders_without_used_ticket(self):
        ended = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Ended Event",
            status=EventStatus.COMPLETED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now - timedelta(hours=4),
            end_at=self.now,
            published_at=self.now - timedelta(days=2),
        )
        ended_type = TicketType.objects.create(event=ended, name="Entry", price=0, currency="USD", quantity_total=10)
        no_show_user = User.objects.create_user(username="noshow", email="noshow@test.local", password="Strong-password-2026!")
        present_user = User.objects.create_user(username="present", email="present@test.local", password="Strong-password-2026!")
        outsider = User.objects.create_user(username="outsider", email="outsider@test.local", password="Strong-password-2026!")
        for user in [no_show_user, present_user, outsider]:
            CRMContact.objects.create(organization=self.organization, user=user, email=user.email, name=user.email)
        for user, ticket_status in [(no_show_user, TicketStatus.VALID), (present_user, TicketStatus.USED)]:
            order = TicketOrder.objects.create(event=ended, buyer=user, customer_name=user.email, customer_email=user.email, status=TicketOrderStatus.CONFIRMED, total_amount=0, currency="USD", confirmed_at=self.now)
            Ticket.objects.create(event=ended, ticket_type=ended_type, order=order, owner=user, holder_name=user.email, holder_email=user.email, status=ticket_status, used_at=self.now if ticket_status == TicketStatus.USED else None)
        workflow = self.workflow(name="No-show", trigger=CRMWorkflowTrigger.NO_SHOW, event=ended, trigger_grace_minutes=60)
        self.action(workflow, tag=self.tag)
        process_due_crm_workflows(now=self.now + timedelta(minutes=1))
        emails = set(CRMWorkflowRun.objects.filter(workflow=workflow, status=CRMWorkflowRunStatus.COMPLETED).values_list("contact__email", flat=True))
        self.assertEqual(emails, {no_show_user.email})

    def test_birthday_trigger_is_once_per_contact_per_day(self):
        workflow = self.workflow(name="Birthday", trigger=CRMWorkflowTrigger.BIRTHDAY)
        self.action(workflow, kind=CRMWorkflowActionKind.IN_APP_NOTIFICATION, title="Joyeux anniversaire", message="Belle journée {{ contact.name }}")
        process_due_crm_workflows(now=self.now)
        process_due_crm_workflows(now=self.now + timedelta(minutes=2))
        self.assertEqual(CRMWorkflowRun.objects.filter(workflow=workflow, contact=self.contact).count(), 1)

    def test_segment_condition_is_rechecked_at_trigger_time(self):
        segment = create_segment(
            organization=self.organization,
            actor=self.marketing,
            name="Consentis",
            audience_kind=AudienceKind.ALL,
            marketing_consent_only=True,
        )
        workflow = self.workflow(name="Segment gated", segment=segment)
        self.action(workflow, tag=self.tag)
        self.contact.marketing_consent = MarketingConsent.UNSUBSCRIBED
        self.contact.save(update_fields=["marketing_consent", "updated_at"])
        follow = OrganizationFollow.objects.create(organization=self.organization, user=self.customer)
        emit_follow_trigger(follow.pk)
        run = CRMWorkflowRun.objects.get(workflow=workflow)
        self.assertEqual(run.status, CRMWorkflowRunStatus.SKIPPED)

    def test_event_update_template_rejected_without_event_context_for_follow(self):
        event_template = CampaignTemplate.objects.create(
            organization=self.organization,
            name="Info événement",
            kind=CommunicationKind.EVENT_UPDATE,
            subject="Info",
            body="Changement",
            created_by=self.marketing,
        )
        workflow = self.workflow(name="Invalid event message")
        action = CRMWorkflowAction(
            workflow=workflow,
            position=1,
            kind=CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE,
            template=event_template,
        )
        with self.assertRaises(ValidationError):
            action.full_clean()

    def test_marketing_can_manage_web_workflows_but_finance_cannot(self):
        self.client.force_login(self.marketing)
        response = self.client.get(reverse("automation:crm-workflows", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("automation:crm-workflow-create", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.finance)
        response = self.client.get(reverse("automation:crm-workflows", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 403)

    def test_api_creation_is_permission_scoped(self):
        self.client.force_login(self.marketing)
        response = self.client.post(
            reverse("automation_api:workflow-list"),
            {
                "organization_id": str(self.organization.pk),
                "name": "API workflow",
                "trigger": CRMWorkflowTrigger.ORDER_CONFIRMED,
                "event_id": str(self.event.pk),
                "min_order_amount": "25.00",
                "currency": "USD",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        workflow_id = response.json()["id"]
        action_response = self.client.post(
            reverse("automation_api:workflow-actions", kwargs={"pk": workflow_id}),
            {"position": 1, "kind": CRMWorkflowActionKind.ADD_TAG, "tag_id": str(self.tag.pk)},
            content_type="application/json",
        )
        self.assertEqual(action_response.status_code, 201)

        self.client.force_login(self.finance)
        response = self.client.post(
            reverse("automation_api:workflow-list"),
            {"organization_id": str(self.organization.pk), "name": "Forbidden", "trigger": CRMWorkflowTrigger.FOLLOWED_ORGANIZER},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

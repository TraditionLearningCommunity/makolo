from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import NotificationPreference
from crm.models import CRMContact, MarketingConsent
from crm.selectors import audience_contacts
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from organizations.models import OrganizationFollow
from tickets.models import Ticket, TicketStatus

from .crm_services import (
    _claim_action_run,
    _modify_tag,
    _notify_team,
    _schedule_first_action,
    _schedule_next_action,
    _send_template_email,
    _workflow_matches,
    recover_stale_crm_workflow_actions,
)
from .models import (
    CRMWorkflow,
    CRMWorkflowActionKind,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
    CRMWorkflowRun,
    CRMWorkflowRunStatus,
    CRMWorkflowTrigger,
)


def _emit_specific_workflow(*, workflow, contact, source_type, source_id, event=None, order=None, ticket=None, context=None, now=None):
    """Déclenche exactement un workflow.

    Les déclencheurs temporels utilisent cette fonction afin que deux scénarios
    J-7 et J-1 sur le même événement ne se déclenchent pas simultanément.
    """
    now = now or timezone.now()
    context = context or {}
    matches, reason = _workflow_matches(
        workflow,
        contact=contact,
        event=event,
        order=order,
        ticket=ticket,
        context=context,
    )
    dedup_key = f"crm-workflow:{workflow.pk}:{source_type}:{source_id}:{contact.pk if contact else 'none'}"
    defaults = {
        "workflow": workflow,
        "contact": contact,
        "event": event,
        "order": order,
        "ticket": ticket,
        "source_type": source_type,
        "source_id": str(source_id),
        "context": context,
    }
    if not matches:
        defaults.update(
            status=CRMWorkflowRunStatus.SKIPPED,
            skip_reason=reason[:255],
            completed_at=now,
        )
        CRMWorkflowRun.objects.get_or_create(dedup_key=dedup_key, defaults=defaults)
        return 0
    defaults["status"] = CRMWorkflowRunStatus.WAITING
    run, created = CRMWorkflowRun.objects.get_or_create(dedup_key=dedup_key, defaults=defaults)
    if not created:
        return 0
    _schedule_first_action(run, now=now)
    return 1


def _event_contacts(workflow):
    """Contacts détenteurs de billets, éventuellement intersectés avec un segment."""
    emails = list(
        Ticket.objects.filter(event=workflow.event)
        .exclude(status__in=[TicketStatus.CANCELLED, TicketStatus.REFUNDED])
        .exclude(holder_email="")
        .values_list("holder_email", flat=True)
        .distinct()
    )
    contacts = CRMContact.objects.filter(
        organization=workflow.organization,
        email__in=emails,
    ).select_related("user")
    if workflow.segment_id:
        segment_ids = audience_contacts(workflow.segment).values_list("pk", flat=True)
        contacts = contacts.filter(pk__in=segment_ids)
    return contacts


def _emit_timed_event_workflows(*, now):
    emitted = 0
    workflows = CRMWorkflow.objects.filter(
        is_active=True,
        trigger__in=[CRMWorkflowTrigger.BEFORE_EVENT, CRMWorkflowTrigger.EVENT_ENDED, CRMWorkflowTrigger.NO_SHOW],
        event__isnull=False,
    ).select_related("organization", "event", "segment", "ticket_type")
    for workflow in workflows:
        due_at = (
            workflow.event.start_at - timedelta(minutes=workflow.event_offset_minutes)
            if workflow.trigger == CRMWorkflowTrigger.BEFORE_EVENT
            else workflow.event.end_at
        )
        if now < due_at or now > due_at + timedelta(minutes=workflow.trigger_grace_minutes):
            continue
        contacts = _event_contacts(workflow)
        if workflow.trigger == CRMWorkflowTrigger.NO_SHOW:
            used_emails = {
                value.lower()
                for value in Ticket.objects.filter(event=workflow.event, status=TicketStatus.USED)
                .exclude(holder_email="")
                .values_list("holder_email", flat=True)
            }
            contacts = [contact for contact in contacts if contact.email.lower() not in used_emails]
        for contact in contacts:
            emitted += _emit_specific_workflow(
                workflow=workflow,
                contact=contact,
                source_type="event_clock",
                source_id=f"{workflow.event_id}:{workflow.trigger}:{contact.pk}",
                event=workflow.event,
                context={"due_at": due_at.isoformat()},
                now=now,
            )
    return emitted


def _emit_birthday_workflows(*, now):
    emitted = 0
    local_date = timezone.localdate(now)
    workflows = CRMWorkflow.objects.filter(
        is_active=True,
        trigger=CRMWorkflowTrigger.BIRTHDAY,
    ).select_related("organization", "segment")
    for workflow in workflows:
        contacts = CRMContact.objects.filter(
            organization=workflow.organization,
            user__birth_date__month=local_date.month,
            user__birth_date__day=local_date.day,
        ).select_related("user")
        if workflow.segment_id:
            contacts = contacts.filter(pk__in=audience_contacts(workflow.segment).values_list("pk", flat=True))
        for contact in contacts:
            emitted += _emit_specific_workflow(
                workflow=workflow,
                contact=contact,
                source_type="birthday",
                source_id=f"{contact.pk}:{local_date.isoformat()}",
                context={"birthday": local_date.isoformat()},
                now=now,
            )
    return emitted


def _marketing_notification_allowed(run):
    contact = run.contact
    if not contact or not contact.user_id:
        return False, "Le contact ne possède pas de compte Makolo."
    if contact.marketing_consent != MarketingConsent.SUBSCRIBED:
        return False, "Le contact n’a pas donné de consentement marketing actif."
    preference = NotificationPreference.objects.filter(user_id=contact.user_id).first()
    if preference and not preference.marketing_notifications:
        return False, "Les préférences globales du compte désactivent le marketing."
    follow = OrganizationFollow.objects.filter(
        organization=run.workflow.organization,
        user_id=contact.user_id,
    ).first()
    if follow and not follow.notify_announcements:
        return False, "Les préférences de cet organisateur désactivent ses annonces Makolo."
    return True, ""


def _notify_contact_safe(action_run):
    run = action_run.run
    if not run.contact or not run.contact.user_id:
        return "skipped", {"reason": "Le contact ne possède pas de compte Makolo."}
    if action_run.action.marketing_action:
        allowed, reason = _marketing_notification_allowed(run)
        if not allowed:
            return "skipped", {"reason": reason}
    from .crm_services import _render_text

    title = _render_text(action_run.action.title, run=run)
    message = _render_text(action_run.action.message, run=run)
    action_url = f"/events/{run.event.slug}/" if run.event else "/notifications/"
    create_notification(
        recipient=run.contact.user,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.MARKETING if action_run.action.marketing_action else (NotificationCategory.EVENT if run.event else NotificationCategory.SYSTEM),
        title=title,
        message=message,
        action_url=action_url,
        dedup_key=f"crm-workflow-action:{action_run.pk}",
        metadata={"workflow_id": str(run.workflow_id), "workflow_run_id": str(run.pk)},
        queue_email=False,
    )
    return "completed", {"user_id": str(run.contact.user_id)}


def _perform_action(action_run):
    if not action_run.action.is_active:
        return "skipped", {"reason": "Action désactivée avant son exécution."}
    kind = action_run.action.kind
    if kind == CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE:
        return _send_template_email(action_run)
    if kind == CRMWorkflowActionKind.IN_APP_NOTIFICATION:
        return _notify_contact_safe(action_run)
    if kind == CRMWorkflowActionKind.ADD_TAG:
        return _modify_tag(action_run, add=True)
    if kind == CRMWorkflowActionKind.REMOVE_TAG:
        return _modify_tag(action_run, add=False)
    if kind == CRMWorkflowActionKind.NOTIFY_TEAM:
        return _notify_team(action_run)
    return "skipped", {"reason": "Type d’action inconnu."}


def dispatch_crm_workflow_action(action_run_id, *, now=None):
    now = now or timezone.now()
    action_run = _claim_action_run(action_run_id, now=now)
    if not action_run:
        return "ignored"
    try:
        outcome, output = _perform_action(action_run)
    except Exception as exc:
        action_run.refresh_from_db(fields=["attempts", "max_attempts"])
        terminal = action_run.attempts >= action_run.max_attempts
        retry_at = now + timedelta(minutes=max(action_run.attempts, 1) * 5)
        CRMWorkflowActionRun.objects.filter(pk=action_run.pk).update(
            status=CRMWorkflowActionRunStatus.FAILED if terminal else CRMWorkflowActionRunStatus.QUEUED,
            error=str(exc)[:2000],
            scheduled_for=retry_at,
            updated_at=now,
        )
        if terminal:
            CRMWorkflowRun.objects.filter(pk=action_run.run_id).update(
                status=CRMWorkflowRunStatus.FAILED,
                error=str(exc)[:4000],
                completed_at=now,
                updated_at=now,
            )
            return "failed"
        return "retry"

    final_status = CRMWorkflowActionRunStatus.SKIPPED if outcome == "skipped" else CRMWorkflowActionRunStatus.COMPLETED
    CRMWorkflowActionRun.objects.filter(pk=action_run.pk).update(
        status=final_status,
        output=output,
        error="",
        completed_at=now,
        updated_at=now,
    )
    _schedule_next_action(action_run, now=now)
    return outcome


def process_due_crm_workflows(*, now=None, limit=100):
    now = now or timezone.now()
    stats = {
        "timed_triggers": _emit_timed_event_workflows(now=now),
        "birthdays": _emit_birthday_workflows(now=now),
        "recovered": recover_stale_crm_workflow_actions(now=now),
        "completed": 0,
        "skipped": 0,
        "retry": 0,
        "failed": 0,
        "ignored": 0,
    }
    action_ids = list(
        CRMWorkflowActionRun.objects.filter(
            status=CRMWorkflowActionRunStatus.QUEUED,
            scheduled_for__lte=now,
            run__workflow__is_active=True,
        ).order_by("scheduled_for", "created_at").values_list("pk", flat=True)[:limit]
    )
    for action_id in action_ids:
        outcome = dispatch_crm_workflow_action(action_id, now=now)
        key = "completed" if outcome == "completed" else outcome
        stats[key] = stats.get(key, 0) + 1
    return stats

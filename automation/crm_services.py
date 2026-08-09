from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from crm.models import (
    CommunicationKind,
    ContactSource,
    CRMContact,
    CRMContactTag,
    MarketingConsent,
)
from crm.selectors import audience_contacts
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from organizations.models import OrganizationFollow, OrganizationRole
from tickets.models import Ticket, TicketOrder, TicketStatus

from .models import (
    CRMWorkflow,
    CRMWorkflowActionKind,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
    CRMWorkflowRun,
    CRMWorkflowRunStatus,
    CRMWorkflowTrigger,
)


UNSUBSCRIBE_SIGNING_SALT = "makolo.crm.unsubscribe"


def _public_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = getattr(settings, "MAKOLO_PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/{path.lstrip('/')}" if base else path


def _contact_for_user(organization, user):
    if not user or not user.email:
        return None
    contact = CRMContact.objects.filter(organization=organization, user=user).first()
    if contact:
        return contact
    contact = CRMContact.objects.filter(organization=organization, email__iexact=user.email).first()
    if contact:
        if not contact.user_id:
            contact.user = user
            contact.save(update_fields=["user", "updated_at"])
        return contact
    return CRMContact.objects.create(
        organization=organization,
        user=user,
        email=user.email,
        name=getattr(user, "full_name", "") or user.email,
        source=ContactSource.MANUAL,
    )


def _contact_for_order(order):
    organization = order.event.organization
    if not organization:
        return None
    if order.buyer_id:
        contact = _contact_for_user(organization, order.buyer)
        if contact:
            return contact
    return CRMContact.objects.filter(
        organization=organization,
        email__iexact=order.customer_email,
    ).first()


def _contact_for_ticket(ticket):
    organization = ticket.event.organization
    if not organization:
        return None
    if ticket.owner_id:
        contact = _contact_for_user(organization, ticket.owner)
        if contact:
            return contact
    return CRMContact.objects.filter(
        organization=organization,
        email__iexact=ticket.holder_email,
    ).first()


def _render_text(value, *, run):
    if not value:
        return ""
    contact = run.contact
    event = run.event
    order = run.order
    organization = run.workflow.organization
    replacements = {
        "{{ contact.name }}": contact.display_name if contact else "",
        "{{ contact.email }}": contact.email if contact else "",
        "{{ organization.name }}": organization.name,
        "{{ event.title }}": event.title if event else "",
        "{{ event.start_at }}": timezone.localtime(event.start_at).strftime("%d/%m/%Y %H:%M") if event else "",
        "{{ order.reference }}": order.reference if order else "",
        "{{ order.amount }}": str(order.total_amount) if order else "",
        "{{ order.currency }}": order.currency if order else "",
    }
    rendered = str(value)
    for token, replacement in replacements.items():
        rendered = rendered.replace(token, replacement)
    return rendered


def _email_allowed(contact, template, organization):
    if not contact or not contact.email:
        return False, "Aucune adresse e-mail exploitable."
    if template.kind == CommunicationKind.MARKETING:
        if contact.marketing_consent != MarketingConsent.SUBSCRIBED:
            return False, "Le contact n’a pas donné de consentement marketing actif."
        if contact.user_id:
            preference = NotificationPreference.objects.filter(user_id=contact.user_id).first()
            if preference and (not preference.email_notifications or not preference.marketing_notifications):
                return False, "Les préférences globales du compte désactivent le marketing e-mail."
            follow = OrganizationFollow.objects.filter(
                organization=organization,
                user_id=contact.user_id,
            ).first()
            if follow and (not follow.notify_announcements or not follow.email_announcements):
                return False, "Les préférences de cet organisateur désactivent ses annonces e-mail."
    elif contact.user_id:
        preference = NotificationPreference.objects.filter(user_id=contact.user_id).first()
        if preference and (not preference.email_notifications or not preference.event_notifications):
            return False, "Les préférences du compte désactivent les communications événementielles."
    return True, ""


def _workflow_matches(workflow, *, contact, event=None, order=None, ticket=None, context=None):
    context = context or {}
    if not contact:
        return False, "Aucun contact CRM correspondant."
    if workflow.event_id and (not event or workflow.event_id != event.pk):
        return False, "L’événement ne correspond pas au workflow."
    if workflow.segment_id and not audience_contacts(workflow.segment).filter(pk=contact.pk).exists():
        return False, "Le contact n’appartient plus au segment requis."
    if workflow.min_order_amount is not None:
        if not order or order.total_amount < workflow.min_order_amount:
            return False, "Le montant de commande est inférieur au minimum du workflow."
    if workflow.currency:
        if not order or order.currency.upper() != workflow.currency.upper():
            return False, "La devise de la commande ne correspond pas au workflow."
    if workflow.ticket_type_id:
        matches_type = False
        if ticket and ticket.ticket_type_id == workflow.ticket_type_id:
            matches_type = True
        elif order and order.items.filter(ticket_type_id=workflow.ticket_type_id).exists():
            matches_type = True
        elif str(context.get("ticket_type_id") or "") == str(workflow.ticket_type_id):
            matches_type = True
        if not matches_type:
            return False, "Le type de billet requis n’est pas présent."
    return True, ""


def _schedule_first_action(run, *, now=None):
    now = now or timezone.now()
    action = run.workflow.actions.filter(is_active=True).order_by("position").first()
    if not action:
        run.status = CRMWorkflowRunStatus.COMPLETED
        run.completed_at = now
        run.save(update_fields=["status", "completed_at", "updated_at"])
        return None
    return CRMWorkflowActionRun.objects.get_or_create(
        run=run,
        action=action,
        defaults={"scheduled_for": now + timedelta(minutes=action.delay_minutes)},
    )[0]


@transaction.atomic
def emit_crm_trigger(
    *,
    trigger,
    organization,
    contact,
    source_type,
    source_id,
    event=None,
    order=None,
    ticket=None,
    context=None,
    now=None,
):
    """Crée les parcours correspondant à un événement métier, sans doublon."""
    now = now or timezone.now()
    context = context or {}
    created_count = 0
    workflows = CRMWorkflow.objects.filter(
        organization=organization,
        trigger=trigger,
        is_active=True,
    ).select_related("event", "segment", "ticket_type")
    if event:
        workflows = workflows.filter(Q(event__isnull=True) | Q(event=event))
    for workflow in workflows:
        matches, reason = _workflow_matches(
            workflow,
            contact=contact,
            event=event,
            order=order,
            ticket=ticket,
            context=context,
        )
        dedup_key = f"crm-workflow:{workflow.pk}:{source_type}:{source_id}:{contact.pk if contact else 'none'}"
        if not matches:
            CRMWorkflowRun.objects.get_or_create(
                dedup_key=dedup_key,
                defaults={
                    "workflow": workflow,
                    "contact": contact,
                    "event": event,
                    "order": order,
                    "ticket": ticket,
                    "source_type": source_type,
                    "source_id": str(source_id),
                    "status": CRMWorkflowRunStatus.SKIPPED,
                    "context": context,
                    "skip_reason": reason[:255],
                    "completed_at": now,
                },
            )
            continue
        run, created = CRMWorkflowRun.objects.get_or_create(
            dedup_key=dedup_key,
            defaults={
                "workflow": workflow,
                "contact": contact,
                "event": event,
                "order": order,
                "ticket": ticket,
                "source_type": source_type,
                "source_id": str(source_id),
                "status": CRMWorkflowRunStatus.WAITING,
                "context": context,
            },
        )
        if not created:
            continue
        _schedule_first_action(run, now=now)
        created_count += 1
    return created_count


def emit_follow_trigger(follow_id):
    follow = OrganizationFollow.objects.select_related("organization", "user").filter(pk=follow_id).first()
    if not follow:
        return 0
    contact = _contact_for_user(follow.organization, follow.user)
    return emit_crm_trigger(
        trigger=CRMWorkflowTrigger.FOLLOWED_ORGANIZER,
        organization=follow.organization,
        contact=contact,
        source_type="organization_follow",
        source_id=follow.pk,
    )


def emit_order_trigger(order_id, trigger):
    order = TicketOrder.objects.select_related("event", "event__organization", "buyer").filter(pk=order_id).first()
    if not order or not order.event.organization_id:
        return 0
    contact = _contact_for_order(order)
    return emit_crm_trigger(
        trigger=trigger,
        organization=order.event.organization,
        contact=contact,
        source_type="ticket_order",
        source_id=f"{order.pk}:{trigger}",
        event=order.event,
        order=order,
    )


def emit_waitlist_trigger(waitlist_id):
    from tickets.models import TicketWaitlistEntry

    entry = (
        TicketWaitlistEntry.objects.select_related("ticket_type", "ticket_type__event", "ticket_type__event__organization", "user")
        .filter(pk=waitlist_id)
        .first()
    )
    if not entry or not entry.ticket_type.event.organization_id:
        return 0
    organization = entry.ticket_type.event.organization
    contact = _contact_for_user(organization, entry.user)
    return emit_crm_trigger(
        trigger=CRMWorkflowTrigger.WAITLIST_JOINED,
        organization=organization,
        contact=contact,
        source_type="ticket_waitlist",
        source_id=entry.pk,
        event=entry.ticket_type.event,
        context={"ticket_type_id": str(entry.ticket_type_id), "requested_quantity": entry.requested_quantity},
    )


def emit_checkin_trigger(ticket_id):
    ticket = Ticket.objects.select_related("event", "event__organization", "ticket_type", "order", "owner").filter(pk=ticket_id).first()
    if not ticket or not ticket.event.organization_id or ticket.status != TicketStatus.USED:
        return 0
    contact = _contact_for_ticket(ticket)
    return emit_crm_trigger(
        trigger=CRMWorkflowTrigger.CHECKED_IN,
        organization=ticket.event.organization,
        contact=contact,
        source_type="ticket_checkin",
        source_id=ticket.pk,
        event=ticket.event,
        order=ticket.order,
        ticket=ticket,
        context={"ticket_type_id": str(ticket.ticket_type_id)},
    )


def _event_contacts(workflow):
    event = workflow.event
    if workflow.segment_id:
        return audience_contacts(workflow.segment).select_related("user")
    emails = list(
        Ticket.objects.filter(event=event)
        .exclude(status__in=[TicketStatus.CANCELLED, TicketStatus.REFUNDED])
        .exclude(holder_email="")
        .values_list("holder_email", flat=True)
        .distinct()
    )
    return CRMContact.objects.filter(organization=workflow.organization, email__in=emails).select_related("user")


def _emit_timed_event_workflows(*, now):
    emitted = 0
    workflows = CRMWorkflow.objects.filter(
        is_active=True,
        trigger__in=[CRMWorkflowTrigger.BEFORE_EVENT, CRMWorkflowTrigger.EVENT_ENDED, CRMWorkflowTrigger.NO_SHOW],
        event__isnull=False,
    ).select_related("organization", "event", "segment", "ticket_type")
    for workflow in workflows:
        if workflow.trigger == CRMWorkflowTrigger.BEFORE_EVENT:
            due_at = workflow.event.start_at - timedelta(minutes=workflow.event_offset_minutes)
        else:
            due_at = workflow.event.end_at
        grace_end = due_at + timedelta(minutes=workflow.trigger_grace_minutes)
        if now < due_at or now > grace_end:
            continue

        if workflow.trigger == CRMWorkflowTrigger.NO_SHOW:
            used_emails = set(
                value.lower()
                for value in Ticket.objects.filter(event=workflow.event, status=TicketStatus.USED)
                .exclude(holder_email="")
                .values_list("holder_email", flat=True)
            )
            contacts = [contact for contact in _event_contacts(workflow) if contact.email.lower() not in used_emails]
        else:
            contacts = _event_contacts(workflow)

        for contact in contacts:
            source_id = f"{workflow.event_id}:{workflow.trigger}:{contact.pk}"
            emitted += emit_crm_trigger(
                trigger=workflow.trigger,
                organization=workflow.organization,
                contact=contact,
                source_type="event_clock",
                source_id=source_id,
                event=workflow.event,
                now=now,
                context={"due_at": due_at.isoformat()},
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
            eligible_ids = audience_contacts(workflow.segment).values_list("pk", flat=True)
            contacts = contacts.filter(pk__in=eligible_ids)
        for contact in contacts:
            emitted += emit_crm_trigger(
                trigger=CRMWorkflowTrigger.BIRTHDAY,
                organization=workflow.organization,
                contact=contact,
                source_type="birthday",
                source_id=f"{contact.pk}:{local_date.isoformat()}",
                now=now,
                context={"birthday": local_date.isoformat()},
            )
    return emitted


def _claim_action_run(action_run_id, *, now):
    with transaction.atomic():
        action_run = (
            CRMWorkflowActionRun.objects.select_for_update()
            .select_related(
                "run",
                "run__workflow",
                "run__workflow__organization",
                "run__contact",
                "run__contact__user",
                "run__event",
                "run__order",
                "action",
                "action__template",
                "action__tag",
            )
            .filter(pk=action_run_id)
            .first()
        )
        if not action_run or action_run.status != CRMWorkflowActionRunStatus.QUEUED:
            return None
        if action_run.scheduled_for > now:
            return None
        if action_run.run.status in {CRMWorkflowRunStatus.COMPLETED, CRMWorkflowRunStatus.SKIPPED, CRMWorkflowRunStatus.CANCELLED, CRMWorkflowRunStatus.FAILED}:
            return None
        action_run.status = CRMWorkflowActionRunStatus.PROCESSING
        action_run.attempts += 1
        action_run.error = ""
        action_run.save(update_fields=["status", "attempts", "error", "updated_at"])
        if action_run.run.status == CRMWorkflowRunStatus.WAITING:
            action_run.run.status = CRMWorkflowRunStatus.RUNNING
            action_run.run.started_at = action_run.run.started_at or now
            action_run.run.save(update_fields=["status", "started_at", "updated_at"])
        return action_run


def _send_template_email(action_run):
    run = action_run.run
    action = action_run.action
    template = action.template
    allowed, reason = _email_allowed(run.contact, template, run.workflow.organization)
    if not allowed:
        return "skipped", {"reason": reason}

    unsubscribe_url = ""
    if template.kind == CommunicationKind.MARKETING:
        token = signing.dumps(
            {"contact_id": str(run.contact_id), "campaign_id": None},
            salt=UNSUBSCRIBE_SIGNING_SALT,
            compress=True,
        )
        unsubscribe_url = _public_url(reverse("crm:unsubscribe", kwargs={"token": token}))

    subject = _render_text(template.subject, run=run)
    body = _render_text(template.body, run=run)
    cta_label = _render_text(template.cta_label, run=run)
    cta_url = _render_text(template.cta_url, run=run)
    context = {
        "workflow": run.workflow,
        "contact": run.contact,
        "event": run.event,
        "order": run.order,
        "subject": subject,
        "body": body,
        "cta_label": cta_label,
        "cta_url": cta_url,
        "unsubscribe_url": unsubscribe_url,
    }
    text_body = render_to_string("automation/email/crm_workflow.txt", context)
    html_body = render_to_string("automation/email/crm_workflow.html", context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[run.contact.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)
    return "completed", {"email": run.contact.email, "template_id": str(template.pk)}


def _notify_contact(action_run):
    run = action_run.run
    if not run.contact or not run.contact.user_id:
        return "skipped", {"reason": "Le contact ne possède pas de compte Makolo."}
    title = _render_text(action_run.action.title, run=run)
    message = _render_text(action_run.action.message, run=run)
    action_url = f"/events/{run.event.slug}/" if run.event else "/notifications/"
    create_notification(
        recipient=run.contact.user,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.EVENT if run.event else NotificationCategory.SYSTEM,
        title=title,
        message=message,
        action_url=action_url,
        dedup_key=f"crm-workflow-action:{action_run.pk}",
        metadata={"workflow_id": str(run.workflow_id), "workflow_run_id": str(run.pk)},
        queue_email=False,
    )
    return "completed", {"user_id": str(run.contact.user_id)}


def _modify_tag(action_run, *, add):
    run = action_run.run
    if not run.contact:
        return "skipped", {"reason": "Aucun contact CRM exploitable."}
    if add:
        CRMContactTag.objects.get_or_create(
            contact=run.contact,
            tag=action_run.action.tag,
            defaults={"assigned_by": run.workflow.created_by},
        )
        return "completed", {"tag_id": str(action_run.action.tag_id), "operation": "added"}
    CRMContactTag.objects.filter(contact=run.contact, tag=action_run.action.tag).delete()
    return "completed", {"tag_id": str(action_run.action.tag_id), "operation": "removed"}


def _notify_team(action_run):
    run = action_run.run
    organization = run.workflow.organization
    users = [
        membership.user
        for membership in organization.memberships.filter(
            is_active=True,
            role__in=[OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EVENT_MANAGER, OrganizationRole.MARKETING],
        ).select_related("user")
    ]
    title = _render_text(action_run.action.title, run=run)
    message = _render_text(action_run.action.message, run=run)
    for user in users:
        create_notification(
            recipient=user,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title=title,
            message=message,
            action_url=f"/autopilot/crm/workflows/{run.workflow_id}/",
            dedup_key=f"crm-workflow-team:{action_run.pk}:{user.pk}",
            metadata={"workflow_id": str(run.workflow_id), "workflow_run_id": str(run.pk)},
            queue_email=False,
        )
    return "completed", {"recipients": len(users)}


def _perform_action(action_run):
    kind = action_run.action.kind
    if kind == CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE:
        return _send_template_email(action_run)
    if kind == CRMWorkflowActionKind.IN_APP_NOTIFICATION:
        return _notify_contact(action_run)
    if kind == CRMWorkflowActionKind.ADD_TAG:
        return _modify_tag(action_run, add=True)
    if kind == CRMWorkflowActionKind.REMOVE_TAG:
        return _modify_tag(action_run, add=False)
    if kind == CRMWorkflowActionKind.NOTIFY_TEAM:
        return _notify_team(action_run)
    return "skipped", {"reason": "Type d’action inconnu."}


def _schedule_next_action(action_run, *, now):
    run = action_run.run
    next_action = run.workflow.actions.filter(
        is_active=True,
        position__gt=action_run.action.position,
    ).order_by("position").first()
    if not next_action:
        CRMWorkflowRun.objects.filter(pk=run.pk).update(
            status=CRMWorkflowRunStatus.COMPLETED,
            completed_at=now,
            updated_at=now,
        )
        return None
    next_run, _ = CRMWorkflowActionRun.objects.get_or_create(
        run=run,
        action=next_action,
        defaults={"scheduled_for": now + timedelta(minutes=next_action.delay_minutes)},
    )
    return next_run


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


def recover_stale_crm_workflow_actions(*, now=None, stale_minutes=15):
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=stale_minutes)
    return CRMWorkflowActionRun.objects.filter(
        status=CRMWorkflowActionRunStatus.PROCESSING,
        updated_at__lt=cutoff,
    ).update(
        status=CRMWorkflowActionRunStatus.QUEUED,
        scheduled_for=now,
        error="Reprise automatique après interruption du worker.",
        updated_at=now,
    )


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

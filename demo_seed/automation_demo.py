from __future__ import annotations

from datetime import timedelta

from automation.models import (
    AutomationRun,
    AutomationRunStatus,
    CRMWorkflow,
    CRMWorkflowAction,
    CRMWorkflowActionKind,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
    CRMWorkflowRun,
    CRMWorkflowRunStatus,
    CRMWorkflowTrigger,
    EventAutomationPolicy,
)
from events.models import EventStatus

from .common import SeedContext, backdate, choose, money, upsert


def _seed_automation(ctx: SeedContext) -> None:
    for i, event in enumerate(ctx.events):
        policy = upsert(EventAutomationPolicy, f"event-{event.id}-policy", defaults={
            "event": event,
            "is_active": event.status != EventStatus.CANCELLED,
            "reminder_7d_enabled": i % 2 == 0,
            "reminder_24h_enabled": True,
            "reminder_2h_enabled": True,
            "post_event_followup_enabled": True,
            "auto_complete_event": True,
            "auto_close_sales_at_start": True,
            "capacity_alerts_enabled": True,
            "capacity_alert_percent": choose([70, 80, 90], i),
            "low_stock_alerts_enabled": True,
            "low_stock_threshold": choose([5, 10, 20], i),
        })
        backdate(policy, created_at=event.created_at + timedelta(days=2), updated_at=min(ctx.as_of, event.created_at + timedelta(days=20)))
        for j, rule in enumerate(["reminder_24h", "capacity_alert", "post_event_followup"]):
            if event.start_at > ctx.as_of and j == 2:
                continue
            run_status = choose([AutomationRunStatus.SUCCESS, AutomationRunStatus.SUCCESS, AutomationRunStatus.SKIPPED, AutomationRunStatus.FAILED], i+j)
            created = min(ctx.as_of, event.start_at - timedelta(hours=24) if j == 0 else event.end_at + timedelta(hours=1))
            run = upsert(AutomationRun, f"event-{event.id}-run-{j}", defaults={
                "event": event,
                "rule_key": rule,
                "dedup_key": f"demo:{event.id}:{rule}",
                "status": run_status,
                "summary": "Règle exécutée dans le jeu de démonstration.",
                "payload": {"seed": "makolo-demo", "event": str(event.id)},
                "error": "Provider indisponible, retry simulé." if run_status == AutomationRunStatus.FAILED else "",
            })
            backdate(run, created_at=created)

    for org_index, org in enumerate(ctx.organizations[:7]):
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        contacts = [c for c in ctx.contacts if c.organization_id == org.id]
        templates = list(org.crm_campaign_templates.all())
        tags = list(org.crm_tags.all())
        events = [e for e in ctx.events if e.organization_id == org.id and e.status in {EventStatus.PUBLISHED, EventStatus.COMPLETED}]
        event = events[-1] if events else None
        if not contacts or not templates or not tags:
            continue

        workflow_specs = [
            ("Bienvenue nouvel abonné", CRMWorkflowTrigger.FOLLOWED_ORGANIZER, None),
            ("Après achat confirmé", CRMWorkflowTrigger.ORDER_CONFIRMED, event),
            ("Rappel avant événement", CRMWorkflowTrigger.BEFORE_EVENT, event),
        ]
        for j, (name, trigger, wf_event) in enumerate(workflow_specs):
            first_type = wf_event.ticket_types.first() if wf_event else None
            workflow = upsert(CRMWorkflow, f"org-{org_index}-workflow-{j}", defaults={
                "organization": org,
                "name": name,
                "description": "Parcours CRM multi-étapes de démonstration.",
                "trigger": trigger,
                "event": wf_event,
                "segment": None,
                "ticket_type": first_type if j == 1 else None,
                "min_order_amount": (money("10.00") if first_type and first_type.currency == "USD" else money("20000")) if j == 1 and first_type else None,
                "currency": first_type.currency if j == 1 and first_type else "",
                "event_offset_minutes": 1440 if trigger == CRMWorkflowTrigger.BEFORE_EVENT else 0,
                "trigger_grace_minutes": 120,
                "is_active": True,
                "created_by": owner,
            })
            backdate(workflow, created_at=ctx.as_of - timedelta(days=180+j*15), updated_at=ctx.as_of - timedelta(days=20))

            upsert(CRMWorkflowAction, f"org-{org_index}-workflow-{j}-action-1", defaults={
                "workflow": workflow,
                "position": 1,
                "kind": CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE,
                "delay_minutes": 0,
                "template": templates[j % len(templates)],
                "tag": None,
                "title": "",
                "message": "",
                "marketing_action": False,
                "is_active": True,
            })
            upsert(CRMWorkflowAction, f"org-{org_index}-workflow-{j}-action-2", defaults={
                "workflow": workflow,
                "position": 2,
                "kind": CRMWorkflowActionKind.ADD_TAG,
                "delay_minutes": 60,
                "template": None,
                "tag": tags[j % len(tags)],
                "title": "",
                "message": "",
                "marketing_action": False,
                "is_active": True,
            })
            if j == 0:
                upsert(CRMWorkflowAction, f"org-{org_index}-workflow-{j}-action-3", defaults={
                    "workflow": workflow,
                    "position": 3,
                    "kind": CRMWorkflowActionKind.IN_APP_NOTIFICATION,
                    "delay_minutes": 1440,
                    "template": None,
                    "tag": None,
                    "title": "Bienvenue dans la communauté",
                    "message": "Découvrez les prochains événements de votre organisateur.",
                    "marketing_action": True,
                    "is_active": True,
                })

            contact = contacts[j % len(contacts)]
            order = next((o for o in ctx.orders if o.event.organization_id == org.id and o.buyer_id == contact.user_id), None)
            run_status = choose([CRMWorkflowRunStatus.COMPLETED, CRMWorkflowRunStatus.RUNNING, CRMWorkflowRunStatus.SKIPPED], org_index+j)
            run = upsert(CRMWorkflowRun, f"org-{org_index}-workflow-{j}-run", defaults={
                "workflow": workflow,
                "contact": contact,
                "event": wf_event,
                "order": order if trigger == CRMWorkflowTrigger.ORDER_CONFIRMED else None,
                "ticket": order.tickets.first() if order and order.tickets.exists() else None,
                "source_type": "order" if trigger == CRMWorkflowTrigger.ORDER_CONFIRMED else "organization_follow",
                "source_id": str(order.id if order else contact.id),
                "dedup_key": f"demo-wf-run-{org_index}-{j}",
                "status": run_status,
                "context": {"seed": "makolo-demo", "contact_name": contact.display_name},
                "skip_reason": "Segment non satisfait (démo)." if run_status == CRMWorkflowRunStatus.SKIPPED else "",
                "error": "",
                "started_at": ctx.as_of - timedelta(days=10+j),
                "completed_at": ctx.as_of - timedelta(days=9+j) if run_status == CRMWorkflowRunStatus.COMPLETED else None,
            })
            backdate(run, created_at=ctx.as_of - timedelta(days=10+j), updated_at=ctx.as_of - timedelta(days=9+j))

            for k, action in enumerate(workflow.actions.order_by("position")):
                ar_status = CRMWorkflowActionRunStatus.COMPLETED if run_status == CRMWorkflowRunStatus.COMPLETED else (
                    CRMWorkflowActionRunStatus.QUEUED if run_status == CRMWorkflowRunStatus.RUNNING else CRMWorkflowActionRunStatus.SKIPPED
                )
                ar = upsert(CRMWorkflowActionRun, f"org-{org_index}-workflow-{j}-run-action-{k}", defaults={
                    "run": run,
                    "action": action,
                    "status": ar_status,
                    "scheduled_for": run.started_at + timedelta(minutes=action.delay_minutes) if run.started_at else ctx.as_of,
                    "attempts": 1 if ar_status == CRMWorkflowActionRunStatus.COMPLETED else 0,
                    "max_attempts": 3,
                    "output": {"seed": "makolo-demo", "delivered": ar_status == CRMWorkflowActionRunStatus.COMPLETED},
                    "error": "",
                    "completed_at": run.completed_at if ar_status == CRMWorkflowActionRunStatus.COMPLETED else None,
                })
                backdate(ar, created_at=run.created_at, updated_at=run.updated_at)

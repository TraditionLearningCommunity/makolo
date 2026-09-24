from capacity.services import expire_stale_capacity_reservations
from conversations.automation import process_due_conversation_points
from domain_events.services import process_domain_events, recover_stale_domain_events
from journeys.services import expire_due_journeys
from operations.emergency_controls import is_operational_control_enabled
from operations.models import OperationalControlCode
from recognition.runtime import run_default_recognition_cycle
from sharing.document_services import expire_captures
from spatiotemporal.automation import run_spatiotemporal_automation_cycle

from .crm_runtime import process_due_crm_workflows
from .proactive_preparation import run_proactive_preparation_cycle
from .service_reminders import run_service_reminders
from .services import run_autopilot_cycle as run_legacy_autopilot_cycle
from .subscription_deadlines import run_subscription_deadlines


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    if not is_operational_control_enabled(OperationalControlCode.AUTOPILOT):
        return {"operational_control": "disabled"}
    # Keep every time-driven owner task behind this single cycle so the
    # persistent worker and the scheduled one-shot fallback have identical
    # business coverage. The commands only choose execution cadence.
    stats = {
        "expired_capacity_holds": expire_stale_capacity_reservations(),
        "expired_journeys": expire_due_journeys(),
        "recovered_domain_events": recover_stale_domain_events(),
        "domain_events": process_domain_events(
            batch_size=max(delivery_limit, 1),
            limit=max(delivery_limit, 1),
        ),
    }
    stats.update(
        run_legacy_autopilot_cycle(now=now, delivery_limit=delivery_limit)
    )
    stats["service_reminders"] = run_service_reminders(now=now)
    stats["subscription_deadlines"] = run_subscription_deadlines(now=now)
    stats["spatiotemporal"] = run_spatiotemporal_automation_cycle(
        now=now,
        limit=max(delivery_limit, 1),
    )
    stats["proactive_preparation"] = run_proactive_preparation_cycle(
        now=now,
        limit=max(delivery_limit, 1),
    )
    stats["conversation_points"] = process_due_conversation_points(
        now=now,
        limit=max(delivery_limit, 1),
    )
    stats["recognition"] = run_default_recognition_cycle(now=now)
    stats["expired_inbound_captures"] = expire_captures(limit=500)
    stats["crm_workflows"] = process_due_crm_workflows(
        limit=max(delivery_limit, 1)
    )
    return stats

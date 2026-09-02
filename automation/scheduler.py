from sharing.document_services import expire_captures
from spatiotemporal.automation import run_spatiotemporal_automation_cycle

from .service_reminders import run_service_reminders
from .services import run_autopilot_cycle as run_legacy_autopilot_cycle
from .subscription_deadlines import run_subscription_deadlines


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    """Run canonical automation work plus targeted temporal projections.

    Service reminders remain projections. Subscription deadlines are the narrow
    exception introduced by S5: they dispatch canonical row-locking lifecycle
    services only for rows whose indexed deadline is already due. M6 reuses this
    same scheduler for bounded, provider-free Journey hazard reevaluation rather
    than introducing a second scheduler or per-second polling loop. Sharing also
    performs bounded cleanup of expired inbound captures through the same
    canonical scheduler.
    """
    stats = run_legacy_autopilot_cycle(now=now, delivery_limit=delivery_limit)
    stats["service_reminders"] = run_service_reminders(now=now)
    stats["subscription_deadlines"] = run_subscription_deadlines(now=now)
    stats["spatiotemporal"] = run_spatiotemporal_automation_cycle(
        now=now,
        limit=max(delivery_limit, 1),
    )
    stats["expired_inbound_captures"] = expire_captures(limit=500)
    return stats
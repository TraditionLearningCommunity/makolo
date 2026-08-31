from .service_reminders import run_service_reminders
from .services import run_autopilot_cycle as run_legacy_autopilot_cycle
from .subscription_deadlines import run_subscription_deadlines


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    """Run canonical automation work plus targeted temporal projections.

    Service reminders remain projections. Subscription deadlines are the narrow
    exception introduced by S5: they dispatch canonical row-locking lifecycle
    services only for rows whose indexed deadline is already due.
    """
    stats = run_legacy_autopilot_cycle(now=now, delivery_limit=delivery_limit)
    stats["service_reminders"] = run_service_reminders(now=now)
    stats["subscription_deadlines"] = run_subscription_deadlines(now=now)
    return stats

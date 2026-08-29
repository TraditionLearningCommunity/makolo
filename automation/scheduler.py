from .service_reminders import run_service_reminders
from .services import run_autopilot_cycle as run_legacy_autopilot_cycle


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    """Run the canonical legacy cycle plus T34B temporal projections.

    Services reminders remain projections: they create AutomationRun/Notification rows only
    and never mutate Journey, Requirement, Payment, Opportunity or Subscription state.
    """
    stats = run_legacy_autopilot_cycle(now=now, delivery_limit=delivery_limit)
    stats["service_reminders"] = run_service_reminders(now=now)
    return stats

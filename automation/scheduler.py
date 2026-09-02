from sharing.document_services import expire_captures

from .service_reminders import run_service_reminders
from .services import run_autopilot_cycle as run_legacy_autopilot_cycle
from .subscription_deadlines import run_subscription_deadlines


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    """Run canonical automation work plus targeted temporal projections."""
    stats = run_legacy_autopilot_cycle(now=now, delivery_limit=delivery_limit)
    stats["service_reminders"] = run_service_reminders(now=now)
    stats["subscription_deadlines"] = run_subscription_deadlines(now=now)
    stats["expired_inbound_captures"] = expire_captures(limit=500)
    return stats

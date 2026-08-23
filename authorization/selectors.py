"""Read-side helpers for effective Makolo authority."""

from __future__ import annotations

from .models import Mandate
from .services import _current_mandate_q


def current_mandates(*, at=None):
    """Return Mandates that are effective at ``at`` using the runtime resolver rule.

    Keeping this selector backed by the resolver's canonical predicate prevents
    product surfaces from drifting from ``can()`` on status or validity windows.
    Callers can further constrain the returned queryset by scope and target.
    """

    return Mandate.objects.filter(_current_mandate_q(at), role__is_active=True)

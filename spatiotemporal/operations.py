from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from .types import Hazard, HazardClass, HazardSeverity


def scanner_operational_hazards(occurrence, *, now=None):
    """Adapt existing scanner intelligence for operators only.

    Scanner owns the metrics and incidents. M6 does not infer a participant gate
    recommendation and never exposes this operator projection in Journey context.
    """
    now = now or timezone.now()
    try:
        event = occurrence.activity.event_vertical
    except ObjectDoesNotExist:
        return ()
    from scanner.intelligence import event_access_snapshot

    snapshot = event_access_snapshot(event)
    rows = []
    severity_map = {"high": HazardSeverity.WARNING, "medium": HazardSeverity.NOTICE}
    for incident in snapshot.get("incidents", ()): 
        if incident.get("kind") not in {"gate_congestion", "gate_rejection_rate"}:
            continue
        gate = str(incident.get("gate") or "")
        rows.append(Hazard(
            key=f"scanner:{event.pk}:{incident.get('kind')}:{gate}",
            kind="scanner_congestion",
            hazard_class=HazardClass.INTERNAL,
            severity=severity_map.get(incident.get("severity"), HazardSeverity.INFO),
            audience="operators",
            summary=str(incident.get("title") or incident.get("detail") or "Signal scanner"),
            observed_at=snapshot.get("generated_at") or now,
            source="scanner.intelligence",
            metadata=(("gate", gate),) if gate else (),
        ))
    return tuple(rows)

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from access.models import AccessStatus
from activities.models import OccurrenceStatus

from .types import ActionAdvice, Hazard, HazardClass, HazardSeverity


ADVICE_PRIORITY = {
    "cancelled": 100,
    "access_action": 90,
    "leave_now": 80,
    "warning": 60,
    "information": 20,
}


def _active_access(journey):
    if journey is None:
        return None
    return next(iter(journey.accesses.all()), None)


def get_hazards(*, occurrence, journey=None, mobility=None, now=None):
    now = now or timezone.now()
    hazards = []
    if occurrence.status == OccurrenceStatus.CANCELLED:
        hazards.append(Hazard(
            key=f"occurrence_cancelled:{occurrence.pk}",
            kind="occurrence_cancelled",
            hazard_class=HazardClass.INTERNAL,
            severity=HazardSeverity.CRITICAL,
            audience="participants" if journey is not None else "public",
            summary="Cette occurrence est annulée.",
            observed_at=now,
            source="activities.occurrence",
        ))

    access = _active_access(journey)
    if access is not None and access.status in {AccessStatus.CANCELLED, AccessStatus.REVOKED, AccessStatus.EXPIRED}:
        hazards.append(Hazard(
            key=f"access_unavailable:{access.pk}:{access.status}",
            kind="access_changed",
            hazard_class=HazardClass.INTERNAL,
            severity=HazardSeverity.WARNING,
            audience="specific_journey",
            summary="Votre accès n’est plus utilisable pour cette occurrence.",
            observed_at=now,
            source="access.access",
        ))

    if mobility is not None and mobility.traffic_signal is not None:
        signal = mobility.traffic_signal
        if signal.level in {"heavy", "severe", "disrupted"}:
            hazards.append(Hazard(
                key=f"traffic:{occurrence.pk}:{signal.level}:{signal.observed_at.isoformat()}",
                kind="traffic_delay",
                hazard_class=HazardClass.EXTERNAL,
                severity=HazardSeverity.WARNING,
                audience="specific_journey" if journey is not None else "public",
                summary="Le trafic peut rallonger votre trajet.",
                observed_at=signal.observed_at,
                ends_at=signal.expires_at,
                source=signal.source,
            ))

    if mobility is not None and mobility.weather_signal is not None:
        signal = mobility.weather_signal
        if signal.severity in {HazardSeverity.WARNING, HazardSeverity.CRITICAL}:
            hazards.append(Hazard(
                key=f"weather:{occurrence.pk}:{signal.kind}:{signal.observed_at.isoformat()}",
                kind="severe_weather",
                hazard_class=HazardClass.EXTERNAL,
                severity=signal.severity,
                audience="specific_journey" if journey is not None else "public",
                summary=signal.summary or "Les conditions météo peuvent affecter votre déplacement.",
                observed_at=signal.observed_at,
                ends_at=signal.expires_at,
                source=signal.source,
            ))

    unique = {}
    for hazard in hazards:
        if hazard.ends_at is not None and hazard.ends_at <= now:
            continue
        unique.setdefault(hazard.key, hazard)
    return tuple(unique.values())


def get_action_advices(*, occurrence, journey=None, mobility=None, hazards=(), now=None):
    now = now or timezone.now()
    advices = []
    kinds = {hazard.kind for hazard in hazards}
    if "occurrence_cancelled" in kinds:
        return (ActionAdvice(
            kind="cancelled",
            priority=ADVICE_PRIORITY["cancelled"],
            reason_code="occurrence_cancelled",
            summary="Ne vous déplacez pas : cette occurrence est annulée.",
            observed_at=now,
            source_key=f"occurrence:{occurrence.pk}:cancelled",
        ),)

    if "access_changed" in kinds:
        advices.append(ActionAdvice(
            kind="access_action",
            priority=ADVICE_PRIORITY["access_action"],
            reason_code="access_unavailable",
            summary="Vérifiez votre accès avant de vous déplacer.",
            observed_at=now,
            action_url=reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}) if journey else "",
            source_key=f"journey:{journey.pk}:access" if journey else "",
        ))

    if mobility is not None and mobility.status == "leave_now" and "access_changed" not in kinds:
        advices.append(ActionAdvice(
            kind="leave_now",
            priority=ADVICE_PRIORITY["leave_now"],
            reason_code="leave_soon",
            summary="C’est le moment recommandé pour partir.",
            observed_at=now,
            action_url=mobility.itinerary_url,
            source_key=f"occurrence:{occurrence.pk}:leave_now",
        ))

    for hazard in hazards:
        if hazard.kind in {"traffic_delay", "severe_weather"}:
            advices.append(ActionAdvice(
                kind="warning",
                priority=ADVICE_PRIORITY["warning"],
                reason_code=hazard.kind,
                summary=hazard.summary,
                observed_at=hazard.observed_at,
                action_url=mobility.itinerary_url if mobility else "",
                source_key=hazard.key,
            ))

    advices.sort(key=lambda item: (-item.priority, item.reason_code, item.source_key))
    return tuple(advices)

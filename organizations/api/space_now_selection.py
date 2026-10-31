"""Owner-backed, strictly scoped first vertical Space Now selection.

Now owns neither Occurrences nor Journeys. No empty result here can establish
collective calm: other owner domains are not yet covered by this selector.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from activities.models import Occurrence, OccurrenceStatus, OccurrenceTimingKind
from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission
from journeys.models import Journey, JourneyStatus, WorkflowKind
from services.selectors import service_journeys_visible_to

from .space_work_projection import (
    _activity_scope_from_responsibility,
    _visible_activity_ids,
)


SPACE_NOW_LIMIT = 24
# Bounded source scans do not establish exhaustive coverage; never declare calm.
SOURCE_SCAN_LIMIT = 100


def _situation(
    *, space, source_kind, source_id, activity_id, human_context, subject,
    state, why_now, reason, turn, response_type, destination, web_url,
    observed_at, action_label=None,
):
    source = {"kind": source_kind, "id": str(source_id)}
    owner = {"kind": "activity", "id": str(activity_id)}
    # A handoff is never a mutation. The receiving owner must authorize anew.
    handoff = {
        "type": "owner",
        "target": destination,
        "id": str(source_id) if destination != "activity" else str(activity_id),
    }
    return {
        "id": f"space-now:{space.pk}:{source_kind}:{source_id}",
        "source": source,
        "kind": source_kind,
        "human_context": human_context,
        "subject": {"label": subject},
        "title": human_context,
        "state": {"value": state},
        "state_meaning": state,
        "why_now": {"reason": reason, "meaning": why_now, "basis": [source]},
        # No owner consequence is available. A state change is not proof of one.
        "consequence": {"state": "unknown", "effect": None, "target": source},
        "turn": {"type": turn},
        "response": {"type": response_type, "label": action_label},
        "dimension": "waiting" if response_type == "wait" else "action" if response_type == "act" else "adaptation",
        "exit_condition": {"state": "unknown"},
        "owner_depth": {"source": owner, "links": {"web": web_url}},
        "knowledge_context": {
            "knowledge_state": "known",
            "provenance": [source],
            "freshness": {"state": "unknown", "observed_at": observed_at.isoformat()},
        },
        "links": {"web": web_url, "detail": web_url},
        "handoffs": [handoff],
        "business_actions": (
            [{
                "capability": "open_owner",
                "label": action_label,
                "href": web_url,
                "interaction_depth": "domain_depth",
                "confirmation_required": False,
            }]
            if action_label else []
        ),
        "media_bindings": [],
        "capabilities": [],
    }


def select_space_now(*, profile, space, responsibility_key=None, observed_at=None):
    """Select actual, server-visible attention with no client-side permissions.

    This is intentionally a partial owner coverage, not a broad Work inventory.
    A perspective narrows the scope but cannot grant the owner permissions.
    """
    observed_at = observed_at or timezone.now()
    visible = _visible_activity_ids(profile, space)
    lens = _activity_scope_from_responsibility(profile, space, responsibility_key)
    if lens == set():
        return None
    if lens is not None:
        visible &= lens
    items = []
    scan_incomplete = False

    operation_ids = visible & set(activity_ids_with_direct_permission(
        profile, PermissionCode.ACTIVITY_OPERATIONS_VIEW
    ))
    if operation_ids:
        # Date-only unknown timing cannot be promoted to "currently running".
        near_date = timezone.localdate(observed_at) + timedelta(days=1)
        occurrences = (
            Occurrence.objects.filter(
                activity_id__in=operation_ids,
                status=OccurrenceStatus.SCHEDULED,
            )
            .filter(
                Q(start_at__lte=observed_at)
                | Q(timing_kind=OccurrenceTimingKind.ALL_DAY, start_date__lte=near_date)
            )
            .select_related("activity")
            .order_by("-start_date", "-start_time", "pk")
        )
        candidates = list(occurrences[: SOURCE_SCAN_LIMIT + 1])
        scan_incomplete |= len(candidates) > SOURCE_SCAN_LIMIT
        for occurrence in candidates[:SOURCE_SCAN_LIMIT]:
            if not occurrence.is_ongoing:
                continue
            url = reverse(
                "organizations:space-occurrence-day-of",
                kwargs={"slug": space.slug, "occurrence_id": occurrence.pk},
            )
            items.append(_situation(
                space=space, source_kind="occurrence", source_id=occurrence.pk,
                activity_id=occurrence.activity_id,
                human_context=occurrence.label or occurrence.activity.title,
                subject="Déroulement de l'occurrence",
                state="Occurrence en cours",
                why_now="L'occurrence se déroule actuellement.",
                reason="occurrence_ongoing",
                turn="space", response_type="monitor",
                destination="space_occurrence_day_of", web_url=url,
                observed_at=observed_at, action_label="Suivre le déroulement",
            ))

    review_ids = visible & set(activity_ids_with_direct_permission(
        profile, PermissionCode.ACTIVITY_REQUESTS_VIEW
    ))
    if review_ids:
        requests = (
            Journey.objects.filter(
                activity_id__in=review_ids,
                workflow=WorkflowKind.REGISTRATION,
                status__in=[JourneyStatus.SUBMITTED, JourneyStatus.PENDING_APPROVAL],
            )
            .select_related("activity")
            .order_by("-created_at", "pk")
        )
        candidates = list(requests[: SOURCE_SCAN_LIMIT + 1])
        scan_incomplete |= len(candidates) > SOURCE_SCAN_LIMIT
        decision_ids = set(activity_ids_with_direct_permission(
            profile, PermissionCode.ACTIVITY_REQUESTS_DECIDE
        ))
        for journey in candidates[:SOURCE_SCAN_LIMIT]:
            can_decide = journey.activity_id in decision_ids
            url = reverse("organizations:space-work", kwargs={"slug": space.slug})
            items.append(_situation(
                space=space, source_kind="journey", source_id=journey.pk,
                activity_id=journey.activity_id,
                human_context=journey.activity.title,
                subject="Demande reçue",
                state="Demande en attente d'examen" if journey.status == JourneyStatus.PENDING_APPROVAL else "Demande soumise",
                why_now="Une demande est en attente dans cette activité.",
                reason="registration_request_pending",
                turn="space" if can_decide else "none",
                response_type="decide" if can_decide else "monitor",
                destination="activity", web_url=url,
                observed_at=observed_at,
                action_label="Examiner dans Métier" if can_decide else "Consulter dans Métier",
            ))

    service_ids = visible & (
        set(activity_ids_with_direct_permission(
            profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL
        ))
        | set(activity_ids_with_direct_permission(
            profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED
        ))
    )
    if service_ids:
        cases = (
            service_journeys_visible_to(profile)
            .filter(
                activity_id__in=service_ids,
                status__in=[JourneyStatus.SUBMITTED, JourneyStatus.PENDING_APPROVAL],
            )
            .select_related("activity")
            .order_by("-created_at", "pk")
        )
        candidates = list(cases[: SOURCE_SCAN_LIMIT + 1])
        scan_incomplete |= len(candidates) > SOURCE_SCAN_LIMIT
        for journey in candidates[:SOURCE_SCAN_LIMIT]:
            url = reverse("organizations:space-work", kwargs={"slug": space.slug})
            items.append(_situation(
                space=space, source_kind="journey", source_id=journey.pk,
                activity_id=journey.activity_id, human_context=journey.activity.title,
                subject="Dossier de prestation",
                state="Dossier en attente d'examen" if journey.status == JourneyStatus.PENDING_APPROVAL else "Dossier soumis",
                why_now="Un dossier de prestation attend une suite dans cette activité.",
                reason="service_case_pending",
                turn="none", response_type="monitor",
                destination="activity", web_url=url,
                observed_at=observed_at, action_label="Consulter dans Métier",
            ))

    # Deterministic priority across owner sources; not a generic relevance score.
    order = {"occurrence": 0, "journey": 1}
    items.sort(key=lambda row: (
        order.get(row["source"]["kind"], 2),
        row["human_context"].casefold(),
        row["id"],
    ))
    page = items[:SPACE_NOW_LIMIT]
    return {
        "items": page,
        "has_more": scan_incomplete or len(items) > SPACE_NOW_LIMIT,
        "selection": {
            "state": "partial",
            "reason": "owner_coverage_incomplete",
        },
        "coverage_state": "partial",
        "actor_attention_state": "active" if page else "unknown",
        "freshness": {
            # Time of reading is not the age of the underlying owner facts.
            "state": "unknown",
            "observed_at": observed_at.isoformat(),
        },
    }

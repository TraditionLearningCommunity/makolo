"""Owner-backed, strictly scoped first vertical Space Now selection.

Now owns neither Occurrences nor Journeys. No empty result here can establish
collective calm: other owner domains are not yet covered by this selector.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from activities.models import Occurrence, OccurrenceStatus, OccurrenceTimingKind
from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission
from journeys.collaboration_models import JourneyAssignmentStatus
from journeys.models import JourneyRequest, JourneyStatus, RequestStatus
from services.attention_selectors import facilitator_attention_journeys, manager_attention_journeys
from services.selectors import service_journeys_visible_to

from .space_work_projection import (
    _activity_scope_from_responsibility,
    _visible_activity_ids,
)


def _space_work_url(space, responsibility_key):
    url = reverse("organizations:space-work", kwargs={"slug": space.slug})
    if responsibility_key and responsibility_key != "all":
        return f"{url}?{urlencode({'responsibility': responsibility_key})}"
    return url


# Bounded source scans do not establish exhaustive coverage; never declare calm.
SOURCE_SCAN_LIMIT = 100


def _situation(
    *, space, source_kind, source_id, activity_id, human_context, subject,
    state, why_now, reason, turn, response_type, destination, web_url,
    observed_at, action_label=None, native_id=None, native_link=None,
    deadline_at=None,
):
    source = {"kind": source_kind, "id": str(source_id)}
    owner = source
    # A handoff is never a mutation. The receiving owner must authorize anew.
    handoff = {
        "type": "owner",
        "target": destination,
        "id": str(native_id) if native_id is not None else (
            str(source_id) if destination != "activity" else str(activity_id)
        ),
        **({"link": native_link} if native_link else {}),
        **({"link": f"/space/{space.slug}/retrieval/journey/{source_id}"}
           if destination == "space_work_journey" and not native_link else {}),
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
        "dimension": {
            "wait": "waiting",
            "act": "action",
            "decide": "decision",
        }.get(response_type, "adaptation"),
        "exit_condition": {"state": "unknown"},
        **({"timing": {"deadline_at": deadline_at.isoformat()}}
           if deadline_at is not None else {}),
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
        # Being live is not sufficient. Require a current Operations action.
        from operations.occurrence_live import resolve_occurrence_live
        for occurrence in candidates[:SOURCE_SCAN_LIMIT]:
            if not occurrence.is_ongoing:
                continue
            owner_fact = resolve_occurrence_live(
                occurrence=occurrence, actor=profile, observed_at=observed_at,
            )
            if not owner_fact or owner_fact.get("perspective") not in {"space", "operator"}:
                continue
            action = owner_fact.get("next_action") or {}
            if not action.get("type") or action["type"] == "none":
                continue
            reason = action.get("reason") or "operations_action_required"
            meaning = action.get("label") or "Une intervention opérationnelle est attendue."
            url = reverse(
                "organizations:space-occurrence-day-of",
                kwargs={"slug": space.slug, "occurrence_id": occurrence.pk},
            )
            items.append(_situation(
                space=space, source_kind="occurrence", source_id=occurrence.pk,
                activity_id=occurrence.activity_id,
                human_context=occurrence.label or occurrence.activity.title,
                subject="Intervention opérationnelle",
                state="Intervention signalée par Operations",
                why_now=meaning, reason=reason,
                turn="collective", response_type="act",
                destination="space_occurrence_day_of", web_url=url,
                observed_at=observed_at, action_label="Examiner dans Jour J",
            ))

    review_ids = visible & set(activity_ids_with_direct_permission(
        profile, PermissionCode.ACTIVITY_REQUESTS_VIEW
    ))
    if review_ids:
        # Journey submission alone is not a request for a Space decision.
        # JourneyRequest is the canonical owner of review/approval.
        requests = (
            JourneyRequest.objects.filter(
                journey__activity_id__in=review_ids,
                status=RequestStatus.PENDING,
                journey__status__in=[JourneyStatus.SUBMITTED, JourneyStatus.PENDING_APPROVAL],
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=observed_at)
            )
            .select_related("journey__activity")
            .order_by("-submitted_at", "pk")
        )
        candidates = list(requests[: SOURCE_SCAN_LIMIT + 1])
        scan_incomplete |= len(candidates) > SOURCE_SCAN_LIMIT
        decision_ids = set(activity_ids_with_direct_permission(
            profile, PermissionCode.ACTIVITY_REQUESTS_DECIDE
        ))
        for request in candidates[:SOURCE_SCAN_LIMIT]:
            activity_id = request.journey.activity_id
            can_decide = activity_id in decision_ids
            # Reading remains possible for a viewer without decision power.
            # Console's owner selector revalidates request visibility.
            url = (
                reverse("organizations:console-requests", kwargs={"slug": space.slug})
                + f"?status=pending&activity={activity_id}"
            )
            items.append(_situation(
                space=space, source_kind="journey_request", source_id=request.pk,
                activity_id=activity_id,
                human_context=request.journey.activity.title,
                subject="Demande en attente",
                state="Demande reçue, en attente de décision",
                why_now="Une demande est actuellement en attente d'une décision.",
                reason="journey_request_pending",
                turn="collective" if can_decide else "none",
                response_type="decide" if can_decide else "wait",
                destination="space_request", web_url=url,
                observed_at=observed_at,
                action_label="Examiner la demande" if can_decide else "Consulter la demande",
            ))

    all_case_ids = visible & set(activity_ids_with_direct_permission(
        profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL
    ))
    assigned_case_ids = visible & set(activity_ids_with_direct_permission(
        profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED
    ))
    if all_case_ids or assigned_case_ids:
        # Service's broad visibility selector also admits beneficiary journeys.
        # Space Now must select operator-visible cases, not turn a personal
        # beneficiary journey into an institutional responsibility.
        owner_scope = Q(activity_id__in=all_case_ids)
        if assigned_case_ids:
            owner_scope |= Q(
                activity_id__in=assigned_case_ids,
                assignments__profile=profile,
                assignments__status=JourneyAssignmentStatus.ACTIVE,
            )
        # Use canonical operator-attention selectors, not a generic inventory.
        attention_ids = facilitator_attention_journeys(
            profile, now=observed_at,
        ).values("pk")
        manager_ids = manager_attention_journeys(
            profile, now=observed_at,
        ).values("pk")
        cases = (
            service_journeys_visible_to(profile)
            .filter(
                owner_scope,
            )
            .filter(
                Q(pk__in=attention_ids) | Q(pk__in=manager_ids),
            )
            .exclude(beneficiary=profile)
            .select_related("activity", "service_context")
            .distinct()
            .order_by("-created_at", "pk")
        )
        candidates = list(cases[: SOURCE_SCAN_LIMIT + 1])
        scan_incomplete |= len(candidates) > SOURCE_SCAN_LIMIT
        for journey in candidates[:SOURCE_SCAN_LIMIT]:
            url = (
                reverse("services:operator-case", kwargs={"pk": journey.pk})
                if hasattr(journey, "service_context")
                else _space_work_url(space, responsibility_key)
            )
            items.append(_situation(
                space=space, source_kind="journey", source_id=journey.pk,
                activity_id=journey.activity_id, human_context=journey.activity.title,
                subject="Dossier de prestation",
                state="Suivi opérateur nécessaire",
                why_now="Une situation nécessitant un suivi est établie par Services.",
                reason="service_operator_attention",
                turn="collective", response_type="understand",
                destination="space_work_journey", web_url=url,
                observed_at=observed_at, action_label="Consulter le dossier",
            ))

    # Other domains only contribute explicitly established attention. The
    # projection remains bounded and makes no false global-calm claim.
    from .space_now_domain_signals import select_additional_space_now

    extra, extra_truncated = select_additional_space_now(
        profile=profile, space=space, visible=visible,
        observed_at=observed_at, responsibility_key=responsibility_key,
        make_situation=_situation,
    )
    items.extend(extra)
    scan_incomplete |= extra_truncated

    # Stable owner priority is not a popularity/relevance score.
    order = {
        "operations_incident": 0,
        "occurrence": 1,
        "access_use": 2,
        "capacity_pool": 3,
        "journey_request": 4,
        "payment": 5,
        "commerce_order": 6,
        "journey": 7,
        "automation_execution": 8,
    }
    items.sort(key=lambda row: (
        order.get(row["source"]["kind"], 2),
        row["human_context"].casefold(),
        row["id"],
    ))
    # Do not hide admitted situations behind an arbitrary Top N. Source scans
    # remain bounded for predictable reads and explicit partial coverage.
    return {
        "items": items,
        "has_more": scan_incomplete,
        "selection": {
            "state": "partial",
            "reason": "owner_coverage_incomplete",
        },
        "coverage_state": "partial",
        "actor_attention_state": "active" if items else "unknown",
        "freshness": {
            # Time of reading is not the age of the underlying owner facts.
            "state": "unknown",
            "observed_at": observed_at.isoformat(),
        },
    }

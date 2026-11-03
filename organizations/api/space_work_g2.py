"""MT4: owner-filtered Education and Services relationships for Métier.

A Programme/Prestation is an Activity. A Session is an Occurrence. A
registration or Services case is a Journey. No second source of truth.
Only entries already scoped to a selected authorized Activity may reach here.
"""
from uuid import UUID

from django.urls import reverse
from urllib.parse import urlencode

from journeys.models import Journey, JourneyRequest, RequestStatus, WorkflowKind
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED, service_case_scope,
)
from services.selectors import service_journeys_visible_to

RELATED_LIMIT = 12
_OPERATOR_SCOPES = {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}


def related_g2_work(*, profile, space, activity_id, responsibility, offset,
                    education_ids, service_ids):
    """Bounded, PII-free owner relationships after Work's Activity selection."""
    try:
        owner_id = UUID(str(activity_id))
    except (ValueError, TypeError, AttributeError):
        return None
    if space.archetype == "education":
        if owner_id not in education_ids:
            return {"items": [], "offset": offset, "limit": RELATED_LIMIT,
                    "has_more": False, "coverage_state": "partial"}
        rows = list(
            Journey.objects.filter(
                activity_id=owner_id, workflow=WorkflowKind.REGISTRATION,
            ).order_by("-created_at", "pk")[offset:offset + RELATED_LIMIT + 1]
        )
        request_by_journey = {}
        if rows:
            ids = [row.pk for row in rows[:RELATED_LIMIT]]
            for req in JourneyRequest.objects.filter(
                journey_id__in=ids, status=RequestStatus.PENDING,
            ).order_by("-created_at", "pk").values("journey_id", "pk"):
                request_by_journey.setdefault(req["journey_id"], req["pk"])
        items = []
        for journey in rows[:RELATED_LIMIT]:
            request_id = request_by_journey.get(journey.pk)
            items.append({
                "source": {"kind": "journey", "id": str(journey.pk)},
                "title": "Inscription",
                "state": journey.status,
                "work_label": "Inscription",
                "request_owner": (
                    {"kind": "journey_request", "id": str(request_id)}
                    if request_id else None
                ),
            })
    elif space.archetype == "service_provider":
        if owner_id not in service_ids:
            return {"items": [], "offset": offset, "limit": RELATED_LIMIT,
                    "has_more": False, "coverage_state": "partial"}
        # This selector already applies active case assignments and the
        # CASES_VIEW_ALL scope; never use a generic Journey queryset.
        base = service_journeys_visible_to(profile).filter(
            activity_id=owner_id
        ).exclude(beneficiary=profile)
        # An activity's case can be visible to a delegated operator only; the
        # scope must still be checked for each selected case.
        rows = list(
            base.select_related("activity", "service_context")
            .order_by("-created_at", "pk")[offset:offset + RELATED_LIMIT + 1]
        )
        items = []
        for journey in rows[:RELATED_LIMIT]:
            if service_case_scope(profile, journey) not in _OPERATOR_SCOPES:
                continue
            items.append({
                "source": {"kind": "journey", "id": str(journey.pk)},
                "title": "Dossier de prestation",
                "state": journey.status,
                "work_label": "Dossier de prestation",
                "has_service_context": hasattr(journey, "service_context"),
            })
    else:
        return None
    return {
        "items": items,
        "offset": offset,
        "limit": RELATED_LIMIT,
        "has_more": len(rows) > RELATED_LIMIT,
        "coverage_state": (
            "partial" if offset or len(rows) > RELATED_LIMIT
            else "established"
        ),
    }


def service_case_native_handoff(*, space, journey, responsibility):
    """No mutation implied: owner GET/POST re-checks scope on each call."""
    return (
        reverse(
            "organizations_api:workspace-service-case",
            kwargs={"slug": space.slug, "journey_id": journey.pk},
        ) + "?" + urlencode({"responsibility": responsibility})
    )

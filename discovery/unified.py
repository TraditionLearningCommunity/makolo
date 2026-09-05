from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse

from activities.models import ActivityStatus, ActivityVisibility
from core.participant_presentation import resolve_participant_activity_state
from opportunities.selectors import open_opportunities
from services.models import OpportunityPolicy, ServiceDetails

from .candidate_capabilities import family_can_satisfy_filters, requested_filter_keys


SERVICE_RESULT_LIMIT = 24
OPPORTUNITY_CONTEXT_LIMIT = 1


def _matching_opportunities(text):
    """Only immediately actionable Opportunities may contextualize Service intake."""
    if not text:
        return []
    return list(
        open_opportunities()
        .filter(
            Q(current_revision__title__icontains=text)
            | Q(current_revision__summary__icontains=text)
            | Q(current_revision__issuer_name__icontains=text)
            | Q(current_revision__application_instructions__icontains=text)
        )[:OPPORTUNITY_CONTEXT_LIMIT]
    )


def public_service_discovery_items(
    params,
    *,
    profile=None,
    requested_params=None,
    constraints=(),
):
    """Project public Service Activities into Discover without domain copies.

    Candidate capabilities are evaluated against constraints actually requested
    by the user/interpreter. Technical defaults in a later search mapping must
    not silently remove Service candidates.

    Opportunity remains contextual data for Service intake only when it is open
    now. The Opportunity itself keeps an independent Discovery identity.
    """

    vertical = (params.get("vertical") or "").strip().lower()
    if vertical not in {"", "service"}:
        return []

    requested = requested_filter_keys(
        requested_params=params if requested_params is None else requested_params,
        constraints=constraints,
    )
    if not family_can_satisfy_filters("service_activity", requested):
        return []

    text = (params.get("q") or "").strip()
    services = (
        ServiceDetails.objects.filter(
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
        )
        .exclude(activity__space__verification_status="suspended")
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity__title", "id")
    )
    opportunities = _matching_opportunities(text)
    opportunity = opportunities[0] if opportunities else None

    if text:
        activity_match = (
            Q(activity__title__icontains=text)
            | Q(activity__short_description__icontains=text)
            | Q(activity__description__icontains=text)
            | Q(activity__space__name__icontains=text)
            | Q(activity__owner_profile__first_name__icontains=text)
            | Q(activity__owner_profile__last_name__icontains=text)
            | Q(activity__owner_profile__username__icontains=text)
        )
        if opportunity is None:
            services = services.filter(activity_match)
        else:
            services = services.filter(activity_match | ~Q(opportunity_policy=OpportunityPolicy.NONE))

    rows = []
    seen_activity_ids = set()
    for service in services.distinct()[:SERVICE_RESULT_LIMIT]:
        activity = service.activity
        if activity.pk in seen_activity_ids:
            continue
        seen_activity_ids.add(activity.pk)
        contextual_opportunity = (
            opportunity if opportunity is not None and service.opportunity_policy != OpportunityPolicy.NONE else None
        )
        start_url = reverse("services:start", kwargs={"pk": service.pk})
        if contextual_opportunity is not None:
            start_url = f"{start_url}?{urlencode({'opportunity': contextual_opportunity.pk})}"
        participant = resolve_participant_activity_state(
            profile=profile,
            activity=activity,
            occurrence=None,
            context=None,
            acquisition_label="Commencer l’accompagnement",
            acquisition_url=start_url,
            detail_url=start_url,
        )
        rows.append(
            {
                "candidate_family": "service_activity",
                "candidate_key": f"service_activity:{activity.pk}",
                "activity_id": str(activity.pk),
                "service_id": str(service.pk),
                "vertical": "service",
                "vertical_label": "Accompagnement",
                "title": activity.title,
                "summary": activity.short_description or activity.description[:220],
                "space_name": activity.operator_display_name,
                "service_kind": service.get_service_kind_display(),
                "opportunity_title": (
                    contextual_opportunity.current_revision.title if contextual_opportunity is not None else ""
                ),
                "participant": participant,
                "cta_label": participant.primary_action,
                "cta_url": participant.primary_url,
                "url": start_url,
            }
        )
    return rows

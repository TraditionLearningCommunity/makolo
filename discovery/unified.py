from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse

from activities.models import ActivityStatus, ActivityVisibility
from core.participant_presentation import resolve_participant_activity_state
from opportunities.selectors import published_opportunities
from services.models import OpportunityPolicy, ServiceDetails


SERVICE_RESULT_LIMIT = 24
OPPORTUNITY_CONTEXT_LIMIT = 1


def _matching_opportunities(text):
    if not text:
        return []
    return list(
        published_opportunities()
        .filter(
            Q(current_revision__title__icontains=text)
            | Q(current_revision__summary__icontains=text)
            | Q(current_revision__issuer_name__icontains=text)
            | Q(current_revision__application_instructions__icontains=text)
        )[:OPPORTUNITY_CONTEXT_LIMIT]
    )


def public_service_discovery_items(params, *, profile=None):
    """Project public Service Activities into Discover without changing domain models.

    Opportunity remains contextual data: when a search matches a published
    Opportunity, Discover proposes compatible accompaniment services and passes
    the canonical Opportunity through the existing Service intake URL.
    """

    vertical = (params.get("vertical") or "").strip().lower()
    if vertical not in {"", "service"}:
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
    for service in services.distinct()[:SERVICE_RESULT_LIMIT]:
        activity = service.activity
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

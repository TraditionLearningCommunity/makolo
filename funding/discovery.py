from types import SimpleNamespace

from django.db.models import Q
from django.urls import reverse

from discovery.candidate_capabilities import family_can_satisfy_filters, requested_filter_keys
from discovery.candidate_identity import CandidateKey
from discovery.card_contract import (
    ActionPresentation,
    DiscoveryCardPresentation,
    FactPresentation,
    ParticipantActionSet,
    RepresentationPresentation,
)
from discovery.representation import resolve_activity_representation

from .selectors import funding_progress, public_fundings


DISCOVERY_FUNDING_CANDIDATE_LIMIT = 500


def public_funding_discovery_items(params, *, requested_params=None, constraints=()):
    vertical = (params.get("vertical") or "").strip().lower()
    if vertical not in {"", "funding"}:
        return []
    requested = requested_filter_keys(
        requested_params=params if requested_params is None else requested_params,
        constraints=constraints,
    )
    if not family_can_satisfy_filters("funding_activity", requested):
        return []
    text = (params.get("q") or "").strip()
    queryset = public_fundings()
    if text:
        queryset = queryset.filter(
            Q(activity__title__icontains=text)
            | Q(activity__short_description__icontains=text)
            | Q(activity__description__icontains=text)
            | Q(activity__space__name__icontains=text)
            | Q(activity__owner_profile__first_name__icontains=text)
            | Q(activity__owner_profile__last_name__icontains=text)
            | Q(activity__owner_profile__username__icontains=text)
        ).distinct()
    rows = []
    for funding in queryset[:DISCOVERY_FUNDING_CANDIDATE_LIMIT]:
        activity = funding.activity
        rows.append(
            {
                "candidate_key": str(CandidateKey("funding_activity", str(activity.pk))),
                "activity_id": str(activity.pk),
                "funding": funding,
                "progress": funding_progress(funding),
            }
        )
    return rows


def present_funding_card(item, *, bookmarked=False):
    funding = item["funding"]
    activity = funding.activity
    progress = item["progress"]
    facts = [FactPresentation("raised", "Réuni", f"Réuni : {progress.raised_amount} {progress.currency}", "wallet-cards", 10)]
    if progress.target_amount is not None:
        facts.append(FactPresentation("target", "Objectif", f"Objectif : {progress.target_amount} {progress.currency}", "target", 20))
        if progress.exceeded_amount > 0:
            facts.append(FactPresentation("progress", "Progression", f"Objectif dépassé de {progress.exceeded_amount} {progress.currency} ✓", "circle-check", 30))
        elif progress.target_reached:
            facts.append(FactPresentation("progress", "Progression", "Objectif atteint ✓", "circle-check", 30))
        else:
            facts.append(FactPresentation("remaining", "Reste", f"Reste : {progress.remaining_amount} {progress.currency}", "move-right", 30))
    detail_url = reverse("funding:detail", kwargs={"pk": funding.pk})
    representation = resolve_activity_representation(activity=activity) or RepresentationPresentation(kind="identity", eyebrow="Financement")
    return DiscoveryCardPresentation(
        candidate_key=item["candidate_key"],
        activity_id=str(activity.pk),
        occurrence_id=None,
        presentation_kind="funding",
        vertical_label="Financement",
        title=activity.title,
        summary=activity.short_description or activity.description[:220],
        operator_label="Porté par",
        operator_name=activity.operator_display_name,
        representation=representation,
        facts=tuple(facts),
        participant_state=SimpleNamespace(label="", secondary_label=""),
        actions=ParticipantActionSet(
            save=ActionPresentation(
                code="save",
                role="save",
                label="Enregistré" if bookmarked else "Enregistrer",
                icon="orbit",
                state="saved" if bookmarked else "available",
                url=reverse("discovery:activity-bookmark-toggle", args=[activity.pk]),
            ),
            primary=ActionPresentation(
                code="contribute",
                role="primary",
                label="Contribuer",
                icon="wallet-cards",
                state="available",
                url=detail_url,
                emphasis="primary",
            ),
            share=ActionPresentation(
                code="share",
                role="share",
                label="Partager",
                icon="share-2",
                state="available",
                url=reverse("sharing:create-activity", args=[activity.pk]),
            ),
        ),
        url=detail_url,
    )

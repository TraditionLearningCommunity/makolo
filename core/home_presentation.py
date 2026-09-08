from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from activities.models import OccurrenceStatus, OccurrenceTimingKind
from conversations.attention import attention_points_for_profile
from conversations.point_models import ConversationPoint
from conversations.presentation import conversation_context_label
from journeys.models import Journey
from objectives.models import DossierLifecycle
from objectives.readiness import resolve_dossier_readiness
from objectives.selectors import dossiers_for_profile
from opportunities.models import OpportunityPublicationStatus
from opportunities.selectors import saved_opportunities
from preparation.contextual_actions import (
    ContextualAction,
    ContextualActionIdentity,
    ContextualActionPriority,
    ContextualActionability,
    ContextualDeadlineState,
    actions_from_action_advices,
    actions_from_dossier,
    actions_from_prepared_start,
    actions_from_readiness,
    classify_contextual_deadline,
    resolve_contextual_actions,
)
from preparation.prepared_start import prepared_start_for_revision
from readiness import resolve_many
from readiness.selectors import participant_readiness_queryset
from recognition.selectors import redemptions_requiring_beneficiary_response
from social.models import ActionProposalDirection
from social.profile_search import action_proposals_requiring_actor_response
from spatiotemporal.hazards import get_action_advices, get_hazards

from .participant_presentation import occurrence_timing
from .participant_selectors import ACTIVE_JOURNEY_STATUSES, participant_active_accesses


HOME_JOURNEY_CANDIDATE_LIMIT = 20
HOME_DOSSIER_CANDIDATE_LIMIT = 3
HOME_PREPARED_START_LIMIT = 3
HOME_CONVERSATION_LIMIT = 6
HOME_ACTION_PROPOSAL_LIMIT = 6
HOME_RECOGNITION_LIMIT = 4
HOME_UPCOMING_CANDIDATE_LIMIT = 12
HOME_SECTION_LIMIT = 5
ACTION_PROPOSAL_ACTION_KEY = "respond"


@dataclass(frozen=True, slots=True)
class HomeActionMeta:
    context_label: str
    source_label: str
    fallback_url: str | None = None


@dataclass(frozen=True, slots=True)
class HomeActionItem:
    identity: ContextualActionIdentity
    context_label: str
    source_label: str
    action_label: str
    summary: str
    url: str | None
    status_label: str
    deadline_label: str
    priority: str
    actionability: str


@dataclass(frozen=True, slots=True)
class HomeUpcomingItem:
    access_id: str
    title: str
    timing_label: str
    place_label: str
    url: str


@dataclass(frozen=True, slots=True)
class MatureHomePresentation:
    primary_attention: HomeActionItem | None
    primary_action: HomeActionItem | None
    action_items: tuple[HomeActionItem, ...]
    knowledge_items: tuple[HomeActionItem, ...]
    upcoming: tuple[HomeUpcomingItem, ...]
    all_clear: bool


def _canonical_deadlines(journey):
    deadlines = {}
    if journey.expires_at is not None:
        deadlines["journey.status"] = journey.expires_at
    for step in journey.steps.all():
        if step.due_at is not None:
            deadlines[f"journey.step.{step.pk}"] = step.due_at
    for blocker in journey.blockers.all():
        if blocker.due_at is not None:
            deadlines[f"journey.blocker.{blocker.pk}"] = blocker.due_at
    for obligation in journey.payment_obligations.all():
        if obligation.due_at is not None:
            deadlines[f"payment_obligation.{obligation.pk}"] = obligation.due_at
    for request in journey.form_requests.all():
        if request.due_at is not None:
            deadlines[f"form_request.{request.pk}"] = request.due_at
    return deadlines


def _register_meta(metadata, actions, meta, *, overwrite=False):
    for action in actions:
        if overwrite:
            metadata[action.identity] = meta
        else:
            metadata.setdefault(action.identity, meta)


def _journey_actions(profile, *, observed_at, metadata):
    journeys = list(
        participant_readiness_queryset(
            profile,
            Journey.objects.filter(status__in=ACTIVE_JOURNEY_STATUSES),
        )
        .order_by("-updated_at", "-created_at", "id")[:HOME_JOURNEY_CANDIDATE_LIMIT]
    )
    readiness_by_id = resolve_many(journeys, viewer=profile, observed_at=observed_at)
    actions = []
    for journey in journeys:
        fallback_url = reverse("core:participant-journey-detail", kwargs={"pk": journey.pk})
        meta = HomeActionMeta(
            context_label=journey.activity.title,
            source_label="Démarche",
            fallback_url=fallback_url,
        )
        readiness_actions = actions_from_readiness(
            readiness_by_id[journey.pk],
            context_type="journey",
            context_id=str(journey.pk),
            canonical_deadlines=_canonical_deadlines(journey),
        )
        actions.extend(readiness_actions)
        _register_meta(metadata, readiness_actions, meta)

        if journey.occurrence_id:
            hazards = get_hazards(
                occurrence=journey.occurrence,
                journey=journey,
                mobility=None,
                now=observed_at,
            )
            advices = get_action_advices(
                occurrence=journey.occurrence,
                journey=journey,
                mobility=None,
                hazards=hazards,
                now=observed_at,
            )
            temporal_actions = actions_from_action_advices(
                advices,
                context_type="journey",
                context_id=str(journey.pk),
            )
            actions.extend(temporal_actions)
            _register_meta(
                metadata,
                temporal_actions,
                HomeActionMeta(
                    context_label=journey.activity.title,
                    source_label="Occurrence",
                    fallback_url=fallback_url,
                ),
            )
    return actions


def _dossier_actions(profile, *, observed_at, metadata):
    actions = []
    dossiers = dossiers_for_profile(profile).filter(
        lifecycle__in={DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE}
    ).order_by("-updated_at", "id")[:HOME_DOSSIER_CANDIDATE_LIMIT]
    for dossier in dossiers:
        try:
            readiness = resolve_dossier_readiness(dossier, viewer=profile)
        except PermissionDenied:
            continue
        projected = actions_from_dossier(readiness, observed_at=observed_at)
        actions.extend(projected)
        _register_meta(
            metadata,
            projected,
            HomeActionMeta(
                context_label=dossier.title,
                source_label="Dossier",
                fallback_url=reverse("objectives:dossier-detail", kwargs={"pk": dossier.pk}),
            ),
        )
    return actions


def _prepared_start_actions(profile, *, observed_at, metadata):
    actions = []
    opportunities = saved_opportunities(profile).filter(
        publication_status=OpportunityPublicationStatus.PUBLISHED,
        current_revision__isnull=False,
    )[:HOME_PREPARED_START_LIMIT]
    for opportunity in opportunities:
        revision = opportunity.current_revision
        try:
            prepared = prepared_start_for_revision(
                actor=profile,
                revision=revision,
                observed_at=observed_at,
            )
        except (PermissionDenied, ValidationError):
            continue
        projected = actions_from_prepared_start(prepared)
        actions.extend(projected)
        _register_meta(
            metadata,
            projected,
            HomeActionMeta(
                context_label=revision.title,
                source_label="Préparation",
                fallback_url=reverse("opportunities:detail", kwargs={"pk": opportunity.pk}),
            ),
        )
    return actions


def _proposal_identity(proposal_id):
    proposal_id = str(proposal_id)
    return ContextualActionIdentity(
        source_domain="action_network",
        source_key=f"proposal:{proposal_id}",
        action_key=ACTION_PROPOSAL_ACTION_KEY,
        context_type="action_proposal",
        context_id=proposal_id,
    )


def _presentation_action(
    *,
    identity,
    kind,
    reason_code,
    label,
    summary,
    observed_at,
    priority,
    actionability=ContextualActionability.ACTIONABLE,
    url=None,
    deadline=None,
    mandatory=False,
):
    return ContextualAction(
        identity=identity,
        kind=kind,
        priority=priority,
        actionability=actionability,
        reason_codes=(reason_code,),
        label=label,
        summary=summary,
        observed_at=observed_at,
        url=url,
        deadline=deadline,
        deadline_state=classify_contextual_deadline(deadline, observed_at=observed_at),
        mandatory=mandatory,
    )


def _conversation_actions(profile, *, observed_at, metadata):
    attention = attention_points_for_profile(
        profile,
        at=observed_at,
        limit=HOME_CONVERSATION_LIMIT,
    )
    if not attention:
        return []
    ids = [item.point_id for item in attention]
    points = {
        point.pk: point
        for point in ConversationPoint.objects.filter(pk__in=ids).select_related(
            "conversation",
            "conversation__context__space",
            "conversation__context__group",
            "conversation__context__activity",
            "conversation__context__occurrence__activity",
            "conversation__context__dossier",
            "conversation__context__project",
            "conversation__context__journey__activity",
            "conversation__context__action_proposal__need",
            "conversation__context__direct_profile_a",
            "conversation__context__direct_profile_b",
        )
    }
    labels = {
        "respond": "Répondre",
        "acknowledge": "Confirmer que vous avez vu ce point",
        "form": "Remplir ce qui est demandé",
        "resolve": "Régler ce point",
        "revisit": "Revoir ce point",
    }
    required_reasons = {"respond", "acknowledge", "form", "resolve"}
    actions = []
    for attention_item in attention:
        point = points.get(attention_item.point_id)
        if point is None:
            continue
        context = point.conversation.context
        if getattr(context, "action_proposal_id", None):
            identity = _proposal_identity(context.action_proposal_id)
        else:
            identity = ContextualActionIdentity(
                source_domain="conversations",
                source_key=f"point:{point.pk}",
                action_key=attention_item.reason,
                context_type="conversation",
                context_id=str(point.conversation_id),
            )
        deadline_state = classify_contextual_deadline(
            attention_item.deadline_at,
            observed_at=observed_at,
        )
        if attention_item.reason in required_reasons:
            priority = ContextualActionPriority.P1_REQUIRED
        elif deadline_state in {ContextualDeadlineState.OVERDUE, ContextualDeadlineState.DUE_TODAY}:
            priority = ContextualActionPriority.P2_TIME_CONSTRAINED
        else:
            priority = ContextualActionPriority.P3_PROGRESS
        body = (point.title or point.body or "Une réponse est attendue.").strip()
        if len(body) > 180:
            body = f"{body[:177].rstrip()}…"
        action = _presentation_action(
            identity=identity,
            kind="conversation.attention",
            reason_code=f"conversation.{attention_item.reason}",
            label=labels.get(attention_item.reason, "Ouvrir la conversation"),
            summary=body,
            observed_at=observed_at,
            priority=priority,
            url=f"{reverse('conversations:detail', kwargs={'pk': point.conversation_id})}#point-{point.pk}",
            deadline=attention_item.deadline_at,
            mandatory=attention_item.reason in required_reasons,
        )
        actions.append(action)
        _register_meta(
            metadata,
            (action,),
            HomeActionMeta(
                context_label=conversation_context_label(point.conversation, profile),
                source_label="Conversation",
                fallback_url=action.url,
            ),
        )
    return actions


def _action_proposal_actions(profile, *, observed_at, metadata):
    proposals = list(
        action_proposals_requiring_actor_response(profile, at=observed_at)
        .order_by("expires_at", "created_at", "id")[:HOME_ACTION_PROPOSAL_LIMIT]
    )
    actions = []
    inbox_url = reverse("social:my-solicitations")
    for proposal in proposals:
        if proposal.direction == ActionProposalDirection.OWNER_TO_CANDIDATE:
            summary = f"{proposal.need.owner_display_name} attend votre réponse."
        else:
            summary = "Une proposition attend votre décision pour ce besoin."
        action = _presentation_action(
            identity=_proposal_identity(proposal.pk),
            kind="action_network.response_required",
            reason_code="action_proposal.response_required",
            label="Répondre à la proposition",
            summary=summary,
            observed_at=observed_at,
            priority=ContextualActionPriority.P1_REQUIRED,
            url=inbox_url,
            deadline=proposal.expires_at,
        )
        actions.append(action)
        _register_meta(
            metadata,
            (action,),
            HomeActionMeta(
                context_label=proposal.need.title,
                source_label="Réseau d’action",
                fallback_url=inbox_url,
            ),
            overwrite=True,
        )
    return actions


def _recognition_actions(profile, *, observed_at, metadata):
    actions = []
    dashboard_url = reverse("recognition:dashboard")
    redemptions = redemptions_requiring_beneficiary_response(profile)[:HOME_RECOGNITION_LIMIT]
    for redemption in redemptions:
        action = _presentation_action(
            identity=ContextualActionIdentity(
                source_domain="recognition",
                source_key=f"redemption:{redemption.pk}",
                action_key="beneficiary_decision",
                context_type="recognition_redemption",
                context_id=str(redemption.pk),
            ),
            kind="recognition.beneficiary_decision",
            reason_code="recognition.beneficiary_consent_required",
            label="Accepter ou refuser",
            summary="Un bénéfice vous est proposé et attend votre décision.",
            observed_at=observed_at,
            priority=ContextualActionPriority.P1_REQUIRED,
            url=dashboard_url,
        )
        actions.append(action)
        _register_meta(
            metadata,
            (action,),
            HomeActionMeta(
                context_label=redemption.reward.name,
                source_label="Reconnaissance",
                fallback_url=dashboard_url,
            ),
        )
    return actions


def _status_label(action):
    return {
        ContextualActionability.TERMINAL: "À savoir",
        ContextualActionability.BLOCKING: "Bloqué",
        ContextualActionability.ACTIONABLE: "À faire",
        ContextualActionability.WAITING: "En attente",
        ContextualActionability.ADVICE: "À savoir",
        ContextualActionability.INFORMATION: "À savoir",
    }[action.actionability]


def _deadline_label(action):
    if action.deadline_state == ContextualDeadlineState.OVERDUE:
        return "Échéance dépassée"
    if action.deadline_state == ContextualDeadlineState.DUE_TODAY:
        return "Aujourd’hui"
    if action.deadline_state == ContextualDeadlineState.FUTURE and action.deadline is not None:
        return date_format(timezone.localtime(action.deadline), "D d M")
    return ""


def _project_action(action, metadata):
    meta = metadata.get(
        action.identity,
        HomeActionMeta(context_label="Makolo", source_label="À faire"),
    )
    return HomeActionItem(
        identity=action.identity,
        context_label=meta.context_label,
        source_label=meta.source_label,
        action_label=action.label,
        summary=action.summary,
        url=action.url or meta.fallback_url,
        status_label=_status_label(action),
        deadline_label=_deadline_label(action),
        priority=action.priority.value,
        actionability=action.actionability.value,
    )


def _place_label(occurrence):
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    link = primary or (links[0] if links else None)
    if link is None:
        return ""
    place = link.place
    return " · ".join(part for part in (place.name, place.locality) if part)


def _occurrence_is_relevant(occurrence, *, observed_at):
    if occurrence.status in {OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED}:
        return False
    local_today = observed_at.astimezone(ZoneInfo(occurrence.timezone)).date()
    if occurrence.timing_kind == OccurrenceTimingKind.EXACT:
        if occurrence.start_at is None:
            return False
        if occurrence.end_at is not None and occurrence.end_at <= observed_at:
            return False
        return occurrence.start_at >= observed_at or (
            occurrence.start_at <= observed_at
            and (occurrence.end_at is None or occurrence.end_at > observed_at)
        )
    return (occurrence.end_date or occurrence.start_date) >= local_today


def _upcoming_items(profile, *, observed_at):
    lower_date = (observed_at - timedelta(days=1)).date()
    candidates = list(
        participant_active_accesses(profile, at=observed_at)
        .prefetch_related(None)
        .filter(occurrence__isnull=False, occurrence__start_date__gte=lower_date)
        .prefetch_related("occurrence__place_links__place")
        .order_by("occurrence__start_date", "occurrence__start_time", "id")[:HOME_UPCOMING_CANDIDATE_LIMIT]
    )
    items = []
    for access in candidates:
        occurrence = access.occurrence
        if not _occurrence_is_relevant(occurrence, observed_at=observed_at):
            continue
        timing = occurrence_timing(occurrence)
        if timing is None:
            continue
        items.append(
            HomeUpcomingItem(
                access_id=str(access.pk),
                title=access.activity.title,
                timing_label=timing.compact_label,
                place_label=_place_label(occurrence),
                url=reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
            )
        )
        if len(items) >= HOME_SECTION_LIMIT:
            break
    return tuple(items)


def build_mature_home(profile, *, observed_at=None):
    observed_at = observed_at or timezone.now()
    metadata = {}
    actions = []
    actions.extend(_journey_actions(profile, observed_at=observed_at, metadata=metadata))
    actions.extend(_dossier_actions(profile, observed_at=observed_at, metadata=metadata))
    actions.extend(_prepared_start_actions(profile, observed_at=observed_at, metadata=metadata))
    actions.extend(_conversation_actions(profile, observed_at=observed_at, metadata=metadata))
    actions.extend(_action_proposal_actions(profile, observed_at=observed_at, metadata=metadata))
    actions.extend(_recognition_actions(profile, observed_at=observed_at, metadata=metadata))

    result = resolve_contextual_actions(actions, observed_at=observed_at)
    primary_attention = _project_action(result.primary_attention, metadata) if result.primary_attention else None
    primary_action = _project_action(result.primary_action, metadata) if result.primary_action else None
    primary_identities = {
        item.identity
        for item in (primary_attention, primary_action)
        if item is not None
    }
    action_items = []
    knowledge_items = []
    for action in result.actions:
        if action.identity in primary_identities:
            continue
        item = _project_action(action, metadata)
        if action.actionability in {ContextualActionability.BLOCKING, ContextualActionability.ACTIONABLE}:
            action_items.append(item)
        else:
            knowledge_items.append(item)

    return MatureHomePresentation(
        primary_attention=primary_attention,
        primary_action=primary_action,
        action_items=tuple(action_items[:HOME_SECTION_LIMIT]),
        knowledge_items=tuple(knowledge_items[:HOME_SECTION_LIMIT]),
        upcoming=_upcoming_items(profile, observed_at=observed_at),
        all_clear=not result.actions,
    )

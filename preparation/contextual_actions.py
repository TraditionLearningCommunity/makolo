from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone as datetime_timezone
from enum import Enum
from typing import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.utils import timezone

from readiness.types import NextAction, ReadinessCheck, ReadinessCheckState, ReadinessResult, ReadinessStatus
from spatiotemporal.types import ActionAdvice

from .prepared_start import PreparedRequirementState, PreparedStartResult


class ContextualActionPriority(str, Enum):
    P0_CRITICAL = "p0_critical"
    P1_REQUIRED = "p1_required"
    P2_TIME_CONSTRAINED = "p2_time_constrained"
    P3_PROGRESS = "p3_progress"
    P4_INFORMATION = "p4_information"


class ContextualActionability(str, Enum):
    TERMINAL = "terminal"
    BLOCKING = "blocking"
    ACTIONABLE = "actionable"
    WAITING = "waiting"
    ADVICE = "advice"
    INFORMATION = "information"


class ContextualDeadlineState(str, Enum):
    OVERDUE = "overdue"
    DUE_TODAY = "due_today"
    FUTURE = "future"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ContextualActionIdentity:
    source_domain: str
    source_key: str
    action_key: str
    context_type: str
    context_id: str

    def __post_init__(self):
        for field_name in ("source_domain", "source_key", "action_key", "context_type", "context_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field_name} doit être une identité stable non vide.")


@dataclass(frozen=True, slots=True)
class ContextualAction:
    identity: ContextualActionIdentity
    kind: str
    priority: ContextualActionPriority
    actionability: ContextualActionability
    reason_codes: tuple[str, ...]
    label: str
    summary: str
    observed_at: datetime
    url: str | None = None
    deadline: datetime | None = None
    deadline_state: ContextualDeadlineState = ContextualDeadlineState.NONE
    confirmation_required: bool = False
    mandatory: bool = False

    def __post_init__(self):
        _require_aware(self.observed_at, "observed_at")
        if self.deadline is not None:
            _require_aware(self.deadline, "deadline")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValidationError("kind doit être explicite.")
        if not self.reason_codes or any(not isinstance(code, str) or not code.strip() for code in self.reason_codes):
            raise ValidationError("reason_codes doit contenir au moins un code stable.")

    @property
    def is_actionable(self):
        return self.actionability == ContextualActionability.ACTIONABLE


@dataclass(frozen=True, slots=True)
class ContextualActionResult:
    actions: tuple[ContextualAction, ...]
    primary_attention: ContextualAction | None
    primary_action: ContextualAction | None
    observed_at: datetime

    def __post_init__(self):
        _require_aware(self.observed_at, "observed_at")


_PRIORITY_RANK = {
    ContextualActionPriority.P0_CRITICAL: 0,
    ContextualActionPriority.P1_REQUIRED: 1,
    ContextualActionPriority.P2_TIME_CONSTRAINED: 2,
    ContextualActionPriority.P3_PROGRESS: 3,
    ContextualActionPriority.P4_INFORMATION: 4,
}

_ACTIONABILITY_RANK = {
    ContextualActionability.TERMINAL: 0,
    ContextualActionability.BLOCKING: 1,
    ContextualActionability.ACTIONABLE: 2,
    ContextualActionability.WAITING: 3,
    ContextualActionability.ADVICE: 4,
    ContextualActionability.INFORMATION: 5,
}

_DEADLINE_RANK = {
    ContextualDeadlineState.OVERDUE: 0,
    ContextualDeadlineState.DUE_TODAY: 1,
    ContextualDeadlineState.FUTURE: 2,
    ContextualDeadlineState.NONE: 3,
}

_REQUIRED_READINESS_REASONS = frozenset(
    {
        "payment_required",
        "participant_step_required",
        "participant_response_required",
        "form_response_required",
    }
)

_TERMINAL_READINESS_REASONS = frozenset(
    {
        "occurrence_cancelled",
        "journey_cancelled",
        "journey_expired",
        "request_rejected",
        "form_response_deadline_passed",
    }
)

_M6_ADVICE_POLICY = {
    "cancelled": (ContextualActionPriority.P0_CRITICAL, ContextualActionability.TERMINAL),
    "access_action": (ContextualActionPriority.P0_CRITICAL, ContextualActionability.ACTIONABLE),
    "leave_now": (ContextualActionPriority.P2_TIME_CONSTRAINED, ContextualActionability.ACTIONABLE),
    "warning": (ContextualActionPriority.P4_INFORMATION, ContextualActionability.ADVICE),
    "information": (ContextualActionPriority.P4_INFORMATION, ContextualActionability.INFORMATION),
}


def _require_aware(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or not timezone.is_aware(value):
        raise ValidationError(f"{field_name} doit être un datetime timezone-aware.")
    return value


def _reason_codes(codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(code).strip() for code in codes if str(code).strip()}))


def _url(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def classify_contextual_deadline(deadline: datetime | None, *, observed_at: datetime) -> ContextualDeadlineState:
    _require_aware(observed_at, "observed_at")
    if deadline is None:
        return ContextualDeadlineState.NONE
    _require_aware(deadline, "deadline")
    if deadline < observed_at:
        return ContextualDeadlineState.OVERDUE
    local_deadline = deadline.astimezone(observed_at.tzinfo)
    if local_deadline.date() == observed_at.date():
        return ContextualDeadlineState.DUE_TODAY
    return ContextualDeadlineState.FUTURE


def contextual_action_from_next_action(
    next_action: NextAction,
    *,
    source_key: str,
    reason_codes: Iterable[str],
    context_type: str,
    context_id: str,
    observed_at: datetime,
    priority: ContextualActionPriority = ContextualActionPriority.P3_PROGRESS,
    actionability: ContextualActionability = ContextualActionability.ACTIONABLE,
    kind: str = "readiness.action_required",
    summary: str = "",
    deadline: datetime | None = None,
    confirmation_required: bool = False,
    mandatory: bool = False,
) -> ContextualAction:
    if not isinstance(next_action, NextAction):
        raise ValidationError("NextAction M1 attendu.")
    source_domain = (next_action.source or "readiness").strip()
    reasons = _reason_codes(reason_codes)
    return ContextualAction(
        identity=ContextualActionIdentity(
            source_domain=source_domain,
            source_key=source_key,
            action_key=next_action.key,
            context_type=context_type,
            context_id=str(context_id),
        ),
        kind=kind,
        priority=priority,
        actionability=actionability,
        reason_codes=reasons,
        label=next_action.label,
        summary=summary or next_action.label,
        observed_at=observed_at,
        url=_url(next_action.url),
        deadline=deadline,
        deadline_state=classify_contextual_deadline(deadline, observed_at=observed_at),
        confirmation_required=confirmation_required,
        mandatory=mandatory,
    )


def _readiness_action_priority(
    reason_code: str,
    *,
    blocking: bool,
    deadline_state: ContextualDeadlineState,
) -> ContextualActionPriority:
    if blocking or reason_code in _REQUIRED_READINESS_REASONS:
        return ContextualActionPriority.P1_REQUIRED
    if deadline_state in {ContextualDeadlineState.OVERDUE, ContextualDeadlineState.DUE_TODAY}:
        return ContextualActionPriority.P2_TIME_CONSTRAINED
    return ContextualActionPriority.P3_PROGRESS


def _contextual_action_from_readiness_check(
    check: ReadinessCheck,
    *,
    context_type: str,
    context_id: str,
    observed_at: datetime,
    deadline: datetime | None,
) -> ContextualAction | None:
    if check.state in {ReadinessCheckState.SATISFIED, ReadinessCheckState.NOT_APPLICABLE}:
        return None

    deadline_state = classify_contextual_deadline(deadline, observed_at=observed_at)
    mandatory = bool(check.blocking or check.reason_code in _REQUIRED_READINESS_REASONS)

    if check.state == ReadinessCheckState.BLOCKING:
        actionability = (
            ContextualActionability.TERMINAL
            if check.reason_code in _TERMINAL_READINESS_REASONS
            else ContextualActionability.BLOCKING
        )
        priority = ContextualActionPriority.P0_CRITICAL
    elif check.state == ReadinessCheckState.WAITING:
        actionability = ContextualActionability.WAITING
        priority = ContextualActionPriority.P4_INFORMATION
    else:
        actionability = ContextualActionability.ACTIONABLE
        priority = _readiness_action_priority(
            check.reason_code,
            blocking=check.blocking,
            deadline_state=deadline_state,
        )

    if check.next_action is not None:
        return contextual_action_from_next_action(
            check.next_action,
            source_key=check.key,
            reason_codes=(check.reason_code,),
            context_type=context_type,
            context_id=context_id,
            observed_at=observed_at,
            priority=priority,
            actionability=actionability,
            kind=f"readiness.{check.state.value}",
            summary=check.summary,
            deadline=deadline,
            mandatory=mandatory,
        )

    return ContextualAction(
        identity=ContextualActionIdentity(
            source_domain=check.source,
            source_key=check.key,
            action_key=f"attention:{check.reason_code}",
            context_type=context_type,
            context_id=str(context_id),
        ),
        kind=f"readiness.{check.state.value}",
        priority=priority,
        actionability=actionability,
        reason_codes=(check.reason_code,),
        label=check.summary,
        summary=check.summary,
        observed_at=observed_at,
        deadline=deadline,
        deadline_state=deadline_state,
        mandatory=mandatory,
    )


def actions_from_readiness(
    result: ReadinessResult,
    *,
    context_type: str,
    context_id: str,
    canonical_deadlines: Mapping[str, datetime] | None = None,
) -> tuple[ContextualAction, ...]:
    """Normalize every visible M1 check instead of trusting contributor order.

    ``canonical_deadlines`` is keyed by ``ReadinessCheck.key`` and must only contain
    deadlines from an already-authorized owner projection. R2 never reopens domain
    models to discover a deadline.
    """

    if not isinstance(result, ReadinessResult):
        raise ValidationError("ReadinessResult M1 attendu.")
    deadlines = canonical_deadlines or {}
    actions = []
    for check in result.checks:
        action = _contextual_action_from_readiness_check(
            check,
            context_type=context_type,
            context_id=context_id,
            observed_at=result.observed_at,
            deadline=deadlines.get(check.key),
        )
        if action is not None:
            actions.append(action)
    return tuple(actions)


def actions_from_prepared_start(result: PreparedStartResult) -> tuple[ContextualAction, ...]:
    """Adapt R1 Prepared Start without re-reading Action Memory or Trusted Reuse."""

    if not isinstance(result, PreparedStartResult):
        raise ValidationError("PreparedStartResult R1 attendu.")
    actions = []
    for item in result.requirements:
        state = item.preparation_state
        if state == PreparedRequirementState.READY:
            continue

        next_action = item.readiness_check.next_action
        if state == PreparedRequirementState.REVIEW_REQUIRED:
            priority = ContextualActionPriority.P4_INFORMATION
            actionability = ContextualActionability.WAITING
            fallback_key = "review_requirement"
        elif state == PreparedRequirementState.UNKNOWN:
            # Unknown is not missing or ineligible. Verification is useful, but it is
            # intentionally not promoted to the same certainty as a known mandatory gap.
            priority = ContextualActionPriority.P3_PROGRESS
            actionability = ContextualActionability.ACTIONABLE
            fallback_key = "verify_requirement"
        else:
            priority = (
                ContextualActionPriority.P1_REQUIRED
                if item.mandatory
                else ContextualActionPriority.P3_PROGRESS
            )
            actionability = ContextualActionability.ACTIONABLE
            fallback_key = (
                "confirm_reuse"
                if state == PreparedRequirementState.CONFIRMATION_REQUIRED
                else "prepare_requirement"
            )

        action_key = next_action.key if next_action is not None else fallback_key
        label = next_action.label if next_action is not None else item.title
        reasons = _reason_codes(item.reason_codes or (item.readiness_check.reason_code,))
        actions.append(
            ContextualAction(
                identity=ContextualActionIdentity(
                    source_domain="prepared_start",
                    source_key=f"requirement:{item.requirement_id}",
                    action_key=action_key,
                    context_type="opportunity_revision",
                    context_id=result.revision_id,
                ),
                kind=f"prepared_requirement.{state.value}",
                priority=priority,
                actionability=actionability,
                reason_codes=reasons,
                label=label,
                summary=item.readiness_check.summary,
                observed_at=result.observed_at,
                url=_url(next_action.url) if next_action is not None else None,
                confirmation_required=state == PreparedRequirementState.CONFIRMATION_REQUIRED,
                mandatory=item.mandatory,
            )
        )
    return tuple(actions)


def actions_from_action_advices(
    advices: Iterable[ActionAdvice],
    *,
    context_type: str,
    context_id: str,
) -> tuple[ContextualAction, ...]:
    """Declaratively adapt M6 priorities; M6 remains owner of ActionAdvice facts."""

    actions = []
    for advice in advices:
        if not isinstance(advice, ActionAdvice):
            raise ValidationError("ActionAdvice M6 attendu.")
        if not advice.source_key:
            raise ValidationError("ActionAdvice M6 doit fournir source_key pour une identité R2 stable.")
        priority, actionability = _M6_ADVICE_POLICY.get(
            advice.kind,
            (ContextualActionPriority.P4_INFORMATION, ContextualActionability.ADVICE),
        )
        actions.append(
            ContextualAction(
                identity=ContextualActionIdentity(
                    source_domain="spatiotemporal",
                    source_key=advice.source_key,
                    action_key=advice.kind,
                    context_type=context_type,
                    context_id=str(context_id),
                ),
                kind=f"spatiotemporal.{advice.kind}",
                priority=priority,
                actionability=actionability,
                reason_codes=(advice.reason_code,),
                label=advice.summary,
                summary=advice.summary,
                observed_at=advice.observed_at,
                url=_url(advice.action_url),
            )
        )
    return tuple(actions)


def _dossier_status_policy(status: ReadinessStatus | None):
    if status == ReadinessStatus.BLOCKED:
        return ContextualActionPriority.P0_CRITICAL, ContextualActionability.BLOCKING, "blocked"
    if status == ReadinessStatus.ACTION_REQUIRED:
        return ContextualActionPriority.P1_REQUIRED, ContextualActionability.INFORMATION, "action_required"
    if status == ReadinessStatus.WAITING:
        return ContextualActionPriority.P4_INFORMATION, ContextualActionability.WAITING, "waiting"
    return ContextualActionPriority.P4_INFORMATION, ContextualActionability.INFORMATION, "information"


def actions_from_dossier(result, *, observed_at: datetime) -> tuple[ContextualAction, ...]:
    """Adapt only the privacy-safe D Collective Readiness projection.

    Hidden Journeys are never reopened. A hidden influence remains one opaque Dossier
    attention item. Technical source identity is reused only when D explicitly exposed
    it for a visible beneficiary action; otherwise the fallback identity stays Dossier-
    local so R2 cannot deduplicate by label or URL.
    """

    _require_aware(observed_at, "observed_at")
    dossier_id = str(result.dossier.pk)
    actions = []

    if result.hidden_signal:
        priority, actionability, suffix = _dossier_status_policy(result.status)
        actions.append(
            ContextualAction(
                identity=ContextualActionIdentity(
                    source_domain="dossier",
                    source_key="hidden_influence",
                    action_key=f"attention:{suffix}",
                    context_type="dossier",
                    context_id=dossier_id,
                ),
                kind="dossier.hidden_influence",
                priority=priority,
                actionability=actionability,
                reason_codes=("dossier.hidden_influence",),
                label=result.hidden_signal,
                summary=result.hidden_signal,
                observed_at=observed_at,
            )
        )

    for item in result.visible_items:
        journey_id = str(item.journey_id)
        projected = item.next_action
        if projected is not None:
            source = str(getattr(projected, "source", "") or "")
            source_key = str(getattr(projected, "source_key", "") or "")
            action_key = str(getattr(projected, "key", "") or "")
            reason_code = str(getattr(projected, "reason_code", "") or "")
            has_canonical_identity = bool(source and source_key and action_key)
            if has_canonical_identity:
                deadline_state = ContextualDeadlineState.NONE
                priority = _readiness_action_priority(
                    reason_code,
                    blocking=False,
                    deadline_state=deadline_state,
                )
                identity = ContextualActionIdentity(
                    source_domain=source,
                    source_key=source_key,
                    action_key=action_key,
                    context_type="journey",
                    context_id=journey_id,
                )
                reasons = (reason_code,) if reason_code else ("dossier.projected_next_action",)
                kind = "readiness.action_required"
                mandatory = reason_code in _REQUIRED_READINESS_REASONS
            else:
                # Conservative fallback: do not use human text or URL as identity.
                identity = ContextualActionIdentity(
                    source_domain="dossier",
                    source_key=f"projected_next_action:{journey_id}:{action_key or 'unkeyed'}",
                    action_key=action_key or "projected_next_action",
                    context_type="dossier",
                    context_id=dossier_id,
                )
                reasons = ("dossier.projected_next_action",)
                priority = ContextualActionPriority.P3_PROGRESS
                kind = "dossier.projected_next_action"
                mandatory = False
            actions.append(
                ContextualAction(
                    identity=identity,
                    kind=kind,
                    priority=priority,
                    actionability=ContextualActionability.ACTIONABLE,
                    reason_codes=reasons,
                    label=projected.label,
                    summary=projected.label,
                    observed_at=observed_at,
                    url=_url(projected.url),
                    mandatory=mandatory,
                )
            )
            continue

        if item.status not in {ReadinessStatus.BLOCKED, ReadinessStatus.ACTION_REQUIRED, ReadinessStatus.WAITING}:
            continue
        priority, actionability, suffix = _dossier_status_policy(item.status)
        actions.append(
            ContextualAction(
                identity=ContextualActionIdentity(
                    source_domain="dossier",
                    source_key=f"visible_journey:{journey_id}:{suffix}",
                    action_key=f"attention:{suffix}",
                    context_type="dossier",
                    context_id=dossier_id,
                ),
                kind=f"dossier.visible_item.{suffix}",
                priority=priority,
                actionability=actionability,
                reason_codes=(f"dossier.visible_item.{suffix}",),
                label=item.label,
                summary=item.label,
                observed_at=observed_at,
            )
        )

    return tuple(actions)


def _deadline_distance(action: ContextualAction, *, observed_at: datetime) -> float:
    if action.deadline is None:
        return float("inf")
    return abs((action.deadline - observed_at).total_seconds())


def _identity_sort_key(identity: ContextualActionIdentity):
    return (
        identity.context_type,
        identity.context_id,
        identity.source_domain,
        identity.source_key,
        identity.action_key,
    )


def _action_sort_key(action: ContextualAction, *, observed_at: datetime):
    return (
        _PRIORITY_RANK[action.priority],
        _ACTIONABILITY_RANK[action.actionability],
        _DEADLINE_RANK[action.deadline_state],
        _deadline_distance(action, observed_at=observed_at),
        0 if action.mandatory else 1,
        _identity_sort_key(action.identity),
    )


def _reclassify_deadline(action: ContextualAction, *, observed_at: datetime) -> ContextualAction:
    state = classify_contextual_deadline(action.deadline, observed_at=observed_at)
    if state == action.deadline_state:
        return action
    return replace(action, deadline_state=state)


def _merge_identity_group(group: tuple[ContextualAction, ...], *, observed_at: datetime) -> ContextualAction:
    if len(group) == 1:
        return _reclassify_deadline(group[0], observed_at=observed_at)

    normalized = tuple(_reclassify_deadline(action, observed_at=observed_at) for action in group)
    base = max(
        normalized,
        key=lambda action: (
            action.observed_at.timestamp(),
            action.kind,
            action.url or "",
            action.summary,
        ),
    )
    priority = min((action.priority for action in normalized), key=lambda item: _PRIORITY_RANK[item])
    actionability = min(
        (action.actionability for action in normalized),
        key=lambda item: _ACTIONABILITY_RANK[item],
    )
    deadlines = [action.deadline for action in normalized if action.deadline is not None]
    deadline = min(deadlines) if deadlines else None
    urls = sorted({action.url for action in normalized if action.url})
    url = base.url if base.url in urls else (urls[0] if urls else None)
    labels = sorted({action.label for action in normalized if action.label})
    summaries = sorted({action.summary for action in normalized if action.summary})
    kinds = sorted({action.kind for action in normalized})
    return ContextualAction(
        identity=base.identity,
        kind=kinds[0],
        priority=priority,
        actionability=actionability,
        reason_codes=_reason_codes(code for action in normalized for code in action.reason_codes),
        label=labels[0] if labels else "",
        summary=summaries[0] if summaries else "",
        observed_at=max(action.observed_at for action in normalized),
        url=url,
        deadline=deadline,
        deadline_state=classify_contextual_deadline(deadline, observed_at=observed_at),
        confirmation_required=any(action.confirmation_required for action in normalized),
        mandatory=any(action.mandatory for action in normalized),
    )


def deduplicate_contextual_actions(
    actions: Iterable[ContextualAction],
    *,
    observed_at: datetime,
) -> tuple[ContextualAction, ...]:
    """Deduplicate only exact stable identities, never text, URL or fuzzy similarity."""

    _require_aware(observed_at, "observed_at")
    grouped: dict[ContextualActionIdentity, list[ContextualAction]] = {}
    for action in actions:
        if not isinstance(action, ContextualAction):
            raise ValidationError("ContextualAction attendu.")
        grouped.setdefault(action.identity, []).append(action)
    merged = [
        _merge_identity_group(tuple(grouped[identity]), observed_at=observed_at)
        for identity in sorted(grouped, key=_identity_sort_key)
    ]
    return tuple(merged)


def resolve_contextual_actions(
    actions: Iterable[ContextualAction],
    *,
    observed_at: datetime,
) -> ContextualActionResult:
    """Return a deterministic cross-domain order, primary attention and action."""

    _require_aware(observed_at, "observed_at")
    deduplicated = deduplicate_contextual_actions(actions, observed_at=observed_at)
    ordered = tuple(sorted(deduplicated, key=lambda action: _action_sort_key(action, observed_at=observed_at)))
    primary_attention = ordered[0] if ordered else None

    actionable = [action for action in ordered if action.actionability == ContextualActionability.ACTIONABLE]
    if primary_attention is None:
        primary_action = None
    elif primary_attention.actionability == ContextualActionability.TERMINAL:
        # A terminal fact (for example a cancelled Occurrence) makes lower actions
        # misleading; do not push a payment or departure CTA through it.
        primary_action = None
    elif primary_attention.actionability == ContextualActionability.BLOCKING:
        primary_rank = _PRIORITY_RANK[primary_attention.priority]
        primary_action = next(
            (action for action in actionable if _PRIORITY_RANK[action.priority] <= primary_rank),
            None,
        )
    else:
        primary_action = actionable[0] if actionable else None

    return ContextualActionResult(
        actions=ordered,
        primary_attention=primary_attention,
        primary_action=primary_action,
        observed_at=observed_at,
    )


def _canonical_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require_aware(value, "datetime")
    return value.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")


def _signature(payload: dict, *, prefix: str) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def contextual_action_signature(action: ContextualAction) -> str:
    """Pure R3 comparison contract; display wording and observation time are excluded."""

    payload = {
        "identity": {
            "source_domain": action.identity.source_domain,
            "source_key": action.identity.source_key,
            "action_key": action.identity.action_key,
            "context_type": action.identity.context_type,
            "context_id": action.identity.context_id,
        },
        "kind": action.kind,
        "priority": action.priority.value,
        "actionability": action.actionability.value,
        "reason_codes": sorted(set(action.reason_codes)),
        "url": _url(action.url),
        "deadline": _canonical_datetime(action.deadline),
        "deadline_state": action.deadline_state.value,
        "confirmation_required": action.confirmation_required,
        "mandatory": action.mandatory,
    }
    return _signature(payload, prefix="r2-action-v1")


def contextual_action_result_signature(result: ContextualActionResult) -> str:
    """Order-insensitive action-set signature plus material primary selections."""

    if not isinstance(result, ContextualActionResult):
        raise ValidationError("ContextualActionResult attendu.")
    payload = {
        "actions": sorted(contextual_action_signature(action) for action in result.actions),
        "primary_attention": (
            contextual_action_signature(result.primary_attention)
            if result.primary_attention is not None
            else None
        ),
        "primary_action": (
            contextual_action_signature(result.primary_action)
            if result.primary_action is not None
            else None
        ),
    }
    return _signature(payload, prefix="r2-result-v1")

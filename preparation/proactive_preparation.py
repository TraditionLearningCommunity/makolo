from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from django.core.exceptions import ValidationError

from .contextual_actions import (
    ContextualAction,
    ContextualActionResult,
    contextual_action_result_signature,
)


NOTIFICATION_SIGNATURE_VERSION = "r3-notification-v1"


class PreparationTransitionKind(str, Enum):
    BASELINE = "baseline"
    UNCHANGED = "unchanged"
    NON_MATERIAL = "non_material"
    MATERIAL = "material"


@dataclass(frozen=True, slots=True)
class PreparationTransition:
    kind: PreparationTransitionKind
    projection_changed: bool
    notification_changed: bool
    material: bool
    deadline_only: bool = False
    reasons: tuple[str, ...] = ()


def _identity_payload(action: ContextualAction | None):
    if action is None:
        return None
    identity = action.identity
    return {
        "source_domain": identity.source_domain,
        "source_key": identity.source_key,
        "action_key": identity.action_key,
        "context_type": identity.context_type,
        "context_id": identity.context_id,
    }


def _notification_priority(action: ContextualAction) -> str:
    # P2 is R2's temporal promotion for due/overdue actionable items. Canonical
    # reminder owners already cover that clock movement, so R3 treats P2/P3 as the
    # same notification tier unless another material field changes.
    if action.priority.value == "p2_time_constrained":
        return "p3_progress"
    return action.priority.value


def _material_action_payload(action: ContextualAction | None):
    if action is None:
        return None
    return {
        "identity": _identity_payload(action),
        "priority": _notification_priority(action),
        "actionability": action.actionability.value,
        "mandatory": bool(action.mandatory),
        "confirmation_required": bool(action.confirmation_required),
    }


def _signature(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{NOTIFICATION_SIGNATURE_VERSION}:{hashlib.sha256(encoded).hexdigest()}"


def proactive_notification_signature(result: ContextualActionResult) -> str:
    """Sign only the R2 facts that can materially change current user attention.

    Wording, reasons, URLs, observation time, secondary ordering, and raw deadline
    movement are deliberately excluded. A deadline can still become material when
    R2 promotes priority/actionability or selects a different primary action.
    """
    if not isinstance(result, ContextualActionResult):
        raise ValidationError("ContextualActionResult R2 attendu.")
    return _signature(
        {
            "primary_attention": _material_action_payload(result.primary_attention),
            "primary_action": _material_action_payload(result.primary_action),
        }
    )


def _primary_pair(result: ContextualActionResult):
    return result.primary_attention, result.primary_action


def _same_material_action(previous: ContextualAction | None, current: ContextualAction | None) -> bool:
    return _material_action_payload(previous) == _material_action_payload(current)


def deadline_only_transition(previous: ContextualActionResult, current: ContextualActionResult) -> bool:
    """Return true when only deadline presentation changed for the primary choices.

    R2's full projection signature may move for FUTURE/DUE_TODAY/OVERDUE or an exact
    deadline while R3 remains silent because canonical reminder owners already cover
    pure temporal reminders. If deadline pressure changes priority/actionability, the
    R3 signature changes and this function returns false.
    """
    if not isinstance(previous, ContextualActionResult) or not isinstance(current, ContextualActionResult):
        raise ValidationError("Deux ContextualActionResult R2 sont attendus.")
    if contextual_action_result_signature(previous) == contextual_action_result_signature(current):
        return False
    if proactive_notification_signature(previous) != proactive_notification_signature(current):
        return False

    changed_deadline = False
    for old, new in zip(_primary_pair(previous), _primary_pair(current)):
        if not _same_material_action(old, new):
            return False
        if old is None or new is None:
            continue
        if old.deadline != new.deadline or old.deadline_state != new.deadline_state:
            changed_deadline = True
    return changed_deadline


def _transition_reasons(previous: ContextualActionResult, current: ContextualActionResult) -> tuple[str, ...]:
    reasons = []
    old_attention, old_action = _primary_pair(previous)
    new_attention, new_action = _primary_pair(current)

    if _identity_payload(old_attention) != _identity_payload(new_attention):
        reasons.append("primary_attention_changed")
    if _identity_payload(old_action) != _identity_payload(new_action):
        reasons.append("primary_action_changed")
    if old_action is not None and new_action is None:
        reasons.append("primary_action_disappeared")
    if old_action is None and new_action is not None:
        reasons.append("primary_action_appeared")

    for old, new, prefix in (
        (old_attention, new_attention, "primary_attention"),
        (old_action, new_action, "primary_action"),
    ):
        if old is None or new is None:
            continue
        if old.actionability != new.actionability:
            reasons.append(f"{prefix}_actionability_changed")
        if old.priority != new.priority:
            reasons.append(f"{prefix}_priority_changed")
        if not old.confirmation_required and new.confirmation_required:
            reasons.append(f"{prefix}_confirmation_required")
        if not old.mandatory and new.mandatory:
            reasons.append(f"{prefix}_became_mandatory")

    return tuple(dict.fromkeys(reasons))


def classify_preparation_transition(
    previous: ContextualActionResult | None,
    current: ContextualActionResult,
) -> PreparationTransition:
    """Pure A->B classifier used by tests and by the persisted signature contract."""
    if not isinstance(current, ContextualActionResult):
        raise ValidationError("ContextualActionResult R2 courant attendu.")
    if previous is None:
        return PreparationTransition(
            kind=PreparationTransitionKind.BASELINE,
            projection_changed=True,
            notification_changed=True,
            material=False,
            reasons=("baseline",),
        )
    if not isinstance(previous, ContextualActionResult):
        raise ValidationError("ContextualActionResult R2 précédent attendu.")

    projection_changed = contextual_action_result_signature(previous) != contextual_action_result_signature(current)
    if not projection_changed:
        return PreparationTransition(
            kind=PreparationTransitionKind.UNCHANGED,
            projection_changed=False,
            notification_changed=False,
            material=False,
        )

    notification_changed = proactive_notification_signature(previous) != proactive_notification_signature(current)
    if not notification_changed:
        only_deadline = deadline_only_transition(previous, current)
        return PreparationTransition(
            kind=PreparationTransitionKind.NON_MATERIAL,
            projection_changed=True,
            notification_changed=False,
            material=False,
            deadline_only=only_deadline,
            reasons=("deadline_only",) if only_deadline else ("secondary_or_presentation_only",),
        )

    reasons = _transition_reasons(previous, current) or ("material_primary_contract_changed",)
    return PreparationTransition(
        kind=PreparationTransitionKind.MATERIAL,
        projection_changed=True,
        notification_changed=True,
        material=True,
        reasons=reasons,
    )

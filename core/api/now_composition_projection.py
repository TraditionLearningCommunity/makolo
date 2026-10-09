"""Owner-backed S5 representations of explicit, visible Dossier dependencies.

Presentation borrows the Dossier's existing Readiness read model. It never
persists a new relation, infers dependency by title/time, or reveals a hidden
Journey via an inferred count or member placeholder.
"""

from __future__ import annotations

import hashlib

from django.urls import reverse

from objectives.models import DossierLifecycle
from objectives.readiness import resolve_owned_dossiers_readiness
from objectives.selectors import owned_dossiers_for_profile
from readiness import ReadinessStatus


def _visible_dependency_situation(readiness, *, observed_at):
    """Only an unsatisfied, fully visible owner dependency may produce S5."""
    if readiness.status != ReadinessStatus.BLOCKED:
        return None
    dependency = next(
        (
            item
            for item in readiness.visible_dependencies
            if not item.is_satisfied
            and item.dependent_journey_id != item.required_journey_id
            and item.dependent_label.strip()
            and item.required_label.strip()
        ),
        None,
    )
    if dependency is None:
        return None

    dossier = readiness.dossier
    source = {"kind": "dossier", "id": str(dossier.pk)}
    dependent_id = str(dependency.dependent_journey_id)
    required_id = str(dependency.required_journey_id)
    key_material = f"{dossier.pk}:{dependent_id}:{required_id}"
    identity = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:32]
    url = reverse(
        "objectives:dossier-detail",
        kwargs={"dossier_id": dossier.pk},
    )
    summary = (
        f"{dependency.dependent_label} dépend de "
        f"{dependency.required_label}."
    )
    effect = (
        f"La suite de {dependency.dependent_label} reste bloquée "
        f"par le prérequis {dependency.required_label}."
    )
    return {
        "id": identity,
        "continuity_identity": identity,
        "key": identity,
        "kind": "dossier.visible_dependency",
        "dimension": "composition",
        "source": source,
        "human_context": dossier.title,
        "owner_label": "Dossier",
        "state": "blocked",
        "actionability": "blocking",
        "state_meaning": "Un prérequis entre deux démarches reste actif.",
        "title": dossier.title,
        "summary": summary,
        "why_now": {
            "reason": "dossier.visible_dependency_unsatisfied",
            "meaning": summary,
            "basis": [source],
        },
        "consequence": {
            "state": "known",
            "effect": effect,
            "target": source,
        },
        # Readiness does not attribute the next move to a particular actor.
        "turn": {"type": "none"},
        "response": {
            "type": "understand",
            "label": "Comprendre le prérequis",
        },
        "horizon": None,
        "capabilities": [],
        "links": {"web": url},
        "owner_depth": {"source": source, "links": {"web": url}},
        "handoffs": [{"type": "owner", "target": "dossier", "id": str(dossier.pk)}],
        "relation_members": [
            {
                "id": dependent_id,
                "label": dependency.dependent_label,
                "knowledge_state": "known",
            },
            {
                "id": required_id,
                "label": dependency.required_label,
                "knowledge_state": "known",
            },
        ],
        "relations": [
            {
                "kind": "dependency",
                "member_ids": [dependent_id, required_id],
                "summary": summary,
            }
        ],
        "knowledge_context": {
            "provenance": [source],
            "freshness": {"state": "fresh", "observed_at": observed_at.isoformat()},
            "knowledge_state": "known",
        },
        "attention": {"level": "near"},
        "media_bindings": [],
        "business_actions": [],
        "makolo_preparation": [],
    }


def dossier_dependency_now_situations(profile, *, observed_at):
    """One visible live dependency per owned Dossier; no hidden projections."""
    dossiers = list(
        owned_dossiers_for_profile(profile)
        .filter(lifecycle__in={DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE})
        .order_by("-updated_at", "id")[:18]
    )
    if not dossiers:
        return []
    resolved = resolve_owned_dossiers_readiness(dossiers, viewer=profile)
    situations = []
    for dossier in dossiers:
        item = _visible_dependency_situation(
            resolved[dossier.pk],
            observed_at=observed_at,
        )
        if item is not None:
            situations.append(item)
    return situations

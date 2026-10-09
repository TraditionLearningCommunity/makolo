from __future__ import annotations

import hashlib

from django.core import signing
from django.db import models
from django.urls import reverse
from django.utils import timezone

from objectives.models import DossierLifecycle, ProjectLifecycle
from objectives.readiness import resolve_owned_dossiers_readiness
from objectives.selectors import owned_dossiers_for_profile, owned_projects_for_profile
from payments.models import PaymentStatus
from journeys.models import Journey
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactSensitivity,
    JourneyArtifactStatus,
)
from payments.selectors import get_payments_visible_to
from preparation.contextual_actions import (
    ContextualAction,
    ContextualActionability,
    ContextualDeadlineState,
)
from readiness import ReadinessCheckState, ReadinessStatus, resolve_many
from readiness.selectors import readiness_queryset
from tickets.models import TransferStatus, WaitlistStatus
from tickets.selectors import get_ticket_transfers_visible_to, get_waitlist_entries_visible_to

from core.home_presentation import resolve_mature_home_contextual_actions
from core.participant_selectors import participant_active_accesses, participant_active_journeys
from core.personal_surface_orchestration import (
    pass_now_candidates_through_molongo,
    pass_ongoing_candidates_through_molongo,
)
from core.read_models import build_personal_ongoing_read_model


ONGOING_LIMIT = 18
ONGOING_CONTINUATION_SALT = "makolo.personal.ongoing.v1"

_DECISION_KINDS = {
    "action_network.response_required",
    "recognition.beneficiary_decision",
    "transfer.recipient_decision",
    "waitlist.offer_decision",
}
_CONVERSATION_REQUIRED_REASONS = {
    "conversation.respond",
    "conversation.acknowledge",
    "conversation.form",
    "conversation.resolve",
}
_MEANINGFUL_READY_REASONS = {
    "access_available",
    "capacity_secured",
    "payment_satisfied",
    "request_approved",
    "requirement_satisfied",
}


def _iso(value):
    return value.isoformat() if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _opaque_action_key(action: ContextualAction) -> str:
    identity = action.identity
    raw = "\x1f".join(
        (
            identity.source_domain,
            identity.source_key,
            identity.action_key,
            identity.context_type,
            identity.context_id,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _opaque_continuity_identity(action: ContextualAction) -> str:
    """Identify the owner fact without coupling continuity to its current action."""
    identity = action.identity
    raw = "\x1f".join(
        (
            identity.source_domain,
            identity.source_key,
            identity.context_type,
            identity.context_id,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _source_for_action(action: ContextualAction):
    context_type = action.identity.context_type
    context_id = action.identity.context_id
    kind = {
        "journey": "journey",
        "dossier": "dossier",
        "conversation": "conversation",
        "action_proposal": "action_proposal",
        "recognition_redemption": "recognition_redemption",
        "waitlist": "waitlist",
        "ticket_transfer": "ticket_transfer",
    }.get(context_type)
    if kind is None:
        return None
    return {"kind": kind, "id": str(context_id)}


def _timing_from_action(action: ContextualAction):
    if action.deadline is None:
        return {}
    return {
        "deadline_at": _iso(action.deadline),
        "deadline_state": action.deadline_state.value,
    }


def _now_dimension(action: ContextualAction):
    if action.kind in _DECISION_KINDS:
        return "decision"

    if action.kind == "conversation.attention":
        if not set(action.reason_codes).intersection(_CONVERSATION_REQUIRED_REASONS):
            return None
        return "action"

    if action.kind.startswith("spatiotemporal."):
        suffix = action.kind.removeprefix("spatiotemporal.")
        if suffix == "cancelled":
            return "adaptation"
        if suffix in {"access_action", "leave_now"}:
            return "action"
        return None

    if action.actionability in {
        ContextualActionability.TERMINAL,
        ContextualActionability.BLOCKING,
    }:
        return "adaptation"

    if action.actionability != ContextualActionability.ACTIONABLE:
        return None

    # A canonical future deadline keeps the intervention in En cours until its
    # owner makes it current. Z2 deliberately does not invent a "soon" window.
    if action.deadline_state == ContextualDeadlineState.FUTURE:
        return None

    return "action"


def _action_links(action: ContextualAction):
    identity = action.identity
    links = {}

    if identity.context_type == "conversation":
        links["detail"] = reverse(
            "conversations-api:detail",
            kwargs={"pk": identity.context_id},
        )
        if identity.source_key.startswith("point:"):
            point_id = identity.source_key.split(":", 1)[1]
            reasons = set(action.reason_codes)
            if "conversation.acknowledge" in reasons:
                links["acknowledge"] = reverse(
                    "conversations-api:point-acknowledge",
                    kwargs={"point_pk": point_id},
                )
            elif "conversation.respond" in reasons:
                links["respond"] = reverse(
                    "conversations-api:point-respond",
                    kwargs={"point_pk": point_id},
                )
        return links

    if identity.context_type == "waitlist":
        entry_id = identity.context_id
        links["detail"] = reverse("ticket-waitlist-detail", kwargs={"pk": entry_id})
        links["accept"] = reverse("ticket-waitlist-accept", kwargs={"pk": entry_id})
        links["leave"] = reverse("ticket-waitlist-leave", kwargs={"pk": entry_id})
        return links

    if identity.context_type == "ticket_transfer":
        transfer_id = identity.context_id
        links["detail"] = reverse("ticket-transfers-detail", kwargs={"pk": transfer_id})
        links["accept"] = reverse("ticket-transfers-accept", kwargs={"pk": transfer_id})
        links["decline"] = reverse("ticket-transfers-decline", kwargs={"pk": transfer_id})
        return links

    if identity.context_type == "action_proposal":
        proposal_id = identity.context_id
        links["detail"] = reverse(
            "social-action-proposal-detail",
            kwargs={"proposal_id": proposal_id},
        )
        links["respond"] = reverse(
            "social-action-proposal-respond",
            kwargs={"proposal_id": proposal_id},
        )
        return links

    if identity.context_type == "recognition_redemption":
        redemption_id = identity.context_id
        links["recognition"] = reverse("recognition_api:me")
        links["accept"] = reverse(
            "recognition_api:redemption-decision",
            kwargs={"redemption_id": redemption_id, "decision": "accept"},
        )
        links["decline"] = reverse(
            "recognition_api:redemption-decision",
            kwargs={"redemption_id": redemption_id, "decision": "decline"},
        )
        return links

    return links


def _action_capabilities(action: ContextualAction):
    if action.identity.context_type == "waitlist":
        return ["accept", "leave"]
    if action.identity.context_type == "ticket_transfer":
        return ["accept", "decline"]
    if action.identity.context_type == "action_proposal":
        return ["respond"]
    if action.identity.context_type == "recognition_redemption":
        return ["accept", "decline"]
    if action.kind == "conversation.attention":
        reasons = set(action.reason_codes)
        if "conversation.acknowledge" in reasons:
            return ["acknowledge"]
        if "conversation.respond" in reasons:
            return ["respond"]
    return []


def _serialize_now_action(action: ContextualAction, dimension: str):
    source = _source_for_action(action)
    if source is None:
        return None
    continuity_identity = _opaque_continuity_identity(action)
    return {
        "id": continuity_identity,
        "continuity_identity": continuity_identity,
        "key": _opaque_action_key(action),
        "kind": action.kind,
        "dimension": dimension,
        "source": source,
        "state": action.reason_codes[0] if action.reason_codes else action.actionability.value,
        "actionability": action.actionability.value,
        "title": action.label,
        "summary": action.summary or None,
        "timing": _timing_from_action(action),
        "capabilities": _action_capabilities(action),
        "links": _action_links(action),
    }


def _now_response_type(dimension: str) -> str:
    if dimension == "decision":
        return "decide"
    if dimension == "adaptation":
        return "understand"
    return "act"


def _decorate_now_semantics(
    action: ContextualAction,
    item: dict,
    *,
    observed_at,
) -> None:
    """Expose server-owned Now meaning without copying an owner domain model."""
    source = item["source"]
    reason = action.reason_codes[0] if action.reason_codes else action.actionability.value
    owner_meaning = action.summary or action.label
    dimension = item["dimension"]
    links = item["links"]

    item.update(
        {
            "why_now": {
                "reason": reason,
                "meaning": owner_meaning,
                "basis": [source],
            },
            "consequence": {
                # ContextualAction has no distinct owner consequence field.
                # Do not relabel its summary as a consequence.
                "state": "unknown",
                "effect": None,
                "target": source,
            },
            "state_meaning": owner_meaning,
            # When the owner has not established another actor, adaptation does
            # not manufacture a system actor or transfer responsibility.
            "turn": {"type": "none" if dimension == "adaptation" else "profile"},
            "response": {
                "type": _now_response_type(dimension),
                "label": action.label,
            },
            "horizon": (
                {
                    "type": "temporal",
                    "at": item["timing"]["deadline_at"],
                    "state": item["timing"]["deadline_state"],
                }
                if item["timing"].get("deadline_at")
                else None
            ),
            "owner_depth": {
                "source": source,
                "links": {
                    key: value
                    for key, value in links.items()
                    if key in {"detail", "web", "day_of", "recognition"}
                },
            },
            "knowledge_context": {
                "provenance": [source],
                "freshness": {
                    "state": "fresh",
                    "observed_at": _iso(observed_at),
                },
                "knowledge_state": "known",
            },
            "attention": {
                "level": "near" if dimension == "adaptation" else "foreground",
            },
            "business_actions": [
                {
                    "capability": capability,
                    "label": action.label,
                    "href": links[capability],
                    # No generic mutation is executed from Now. The owner
                    # performs the action with its own permissions and
                    # confirmation; this is a focused owner handoff.
                    "interaction_depth": "focused",
                }
                for capability in item["capabilities"]
                if capability in links
            ],
            "handoffs": [
                {
                    "type": "owner",
                    "target": source["kind"],
                    "id": source["id"],
                }
            ],
        }
    )


def build_personal_now_projection(profile, *, observed_at=None):
    observed_at = observed_at or timezone.now()
    result, metadata = resolve_mature_home_contextual_actions(
        profile,
        observed_at=observed_at,
        include_prepared_start=False,
    )
    actions = pass_now_candidates_through_molongo(result.actions)
    items = []
    for action in actions:
        dimension = _now_dimension(action)
        if dimension is None:
            continue
        item = _serialize_now_action(action, dimension)
        if item is not None:
            meta = metadata.get(action.identity)
            if meta is not None:
                item["human_context"] = meta.context_label
                item["owner_label"] = meta.source_label
                web_url = action.url or meta.fallback_url
                if web_url:
                    item["links"]["web"] = web_url
            items.append((action, item))
    journey_ids = {
        item["source"]["id"]
        for _, item in items
        if item["source"]["kind"] == "journey"
    }
    occurrence_by_journey = {
        str(pk): occurrence_id
        for pk, occurrence_id in Journey.objects.filter(
            pk__in=journey_ids,
            beneficiary=profile,
        ).values_list("pk", "occurrence_id")
        if occurrence_id is not None
    }
    # These artifacts belong to their Journeys, not to Presentation.
    # Only documents already inside a Journey owned by this profile are
    # exposed. The download endpoint independently rechecks authorization.
    artifact_media_by_journey = {}
    if journey_ids:
        artifacts = (
            JourneyArtifact.objects.filter(
                journey_id__in=journey_ids,
                journey__beneficiary=profile,
                status__in=[
                    JourneyArtifactStatus.DRAFT,
                    JourneyArtifactStatus.SUBMITTED,
                    JourneyArtifactStatus.IN_REVIEW,
                    JourneyArtifactStatus.ACCEPTED,
                    JourneyArtifactStatus.REJECTED,
                ],
            )
            .exclude(sensitivity=JourneyArtifactSensitivity.RESTRICTED)
            .order_by("journey_id", "-uploaded_at", "-created_at")
        )
        for artifact in artifacts:
            existing = artifact_media_by_journey.setdefault(
                str(artifact.journey_id), []
            )
            if len(existing) >= 3 or not artifact.file:
                continue
            mime = (artifact.mime_type or "").lower()
            kind = (
                "image" if mime.startswith("image/")
                else "pdf" if mime == "application/pdf"
                else "video" if mime.startswith("video/")
                else "audio" if mime.startswith("audio/")
                else "document" if mime in {
                    "text/plain",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
                else "unknown"
            )
            url = reverse(
                "personal-projections:now-journey-artifact-media",
                kwargs={"artifact_id": artifact.pk},
            )
            original_url = url
            if kind == "document":
                url += "?view=text"
            existing.append({
                "resource_ref": f"journey_artifact:{artifact.pk}",
                "target": "situation",
                "purpose": "prepare",
                "kind": kind,
                "mime_type": mime,
                "label": artifact.title,
                "url": url,
                "download_url": original_url,
                "authorized": True,
                "presentation_rank": "secondary",
            })

    for action, item in items:
        if item["source"]["kind"] != "journey":
            _decorate_now_semantics(action, item, observed_at=observed_at)
            continue
        journey_id = item["source"]["id"]
        item["links"].setdefault(
            "detail",
            f"/api/v1/me/journeys/{journey_id}/",
        )
        occurrence_id = occurrence_by_journey.get(journey_id)
        if occurrence_id is not None:
            item["occurrence"] = {
                "kind": "occurrence",
                "id": str(occurrence_id),
            }
            item["links"]["day_of"] = (
                f"/api/v1/me/occurrences/{occurrence_id}/day-of/"
            )
            if "open_day_of" not in item["capabilities"]:
                item["capabilities"].append("open_day_of")
        _decorate_now_semantics(action, item, observed_at=observed_at)
        media = artifact_media_by_journey.get(journey_id)
        if media:
            item["media_bindings"] = list(media)

    serialized_items = [item for _, item in items]
    is_empty = not serialized_items
    profile_id = str(profile.pk)
    return {
        "surface": "now_me",
        "actor": {"type": "profile", "id": profile_id},
        "viewer": {"type": "profile", "id": profile_id},
        "freshness": {"state": "fresh", "observed_at": _iso(observed_at)},
        "selection": {
            "state": "empty" if is_empty else "ready",
            "reason": "no_current_attention_needed" if is_empty else None,
        },
        "actor_attention_state": "calm" if is_empty else "active",
        "capabilities": [],
        "handoffs": [],
        "items": serialized_items,
        "continuation": None,
        "terminal": {
            "state": "empty" if is_empty else "ok",
            # Human wording remains Presentation; the server owns the state.
            "message": None,
        },
    }


def _occurrence_timing(occurrence):
    if occurrence is None:
        return {}
    timing = {
        "kind": occurrence.timing_kind,
        "timezone": occurrence.timezone,
        "start_date": _date(occurrence.start_date),
        "end_date": _date(occurrence.end_date),
    }
    if occurrence.start_at is not None:
        timing["start_at"] = _iso(occurrence.start_at)
    if occurrence.end_at is not None:
        timing["end_at"] = _iso(occurrence.end_at)
    return {key: value for key, value in timing.items() if value is not None}


def _occurrence_place(occurrence):
    if occurrence is None:
        return None
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    link = primary or (links[0] if links else None)
    if link is None:
        return None
    place = link.place
    return {
        "name": place.name or None,
        "locality": place.locality or None,
    }


def _readiness_deadline(journey, check):
    key = check.key
    if key == "journey.status":
        return journey.expires_at
    if key.startswith("journey.step."):
        wanted = key.removeprefix("journey.step.")
        step = next((item for item in journey.steps.all() if str(item.pk) == wanted), None)
        return step.due_at if step is not None else None
    if key.startswith("journey.blocker."):
        wanted = key.removeprefix("journey.blocker.")
        blocker = next((item for item in journey.blockers.all() if str(item.pk) == wanted), None)
        return blocker.due_at if blocker is not None else None
    if key.startswith("payment_obligation."):
        wanted = key.removeprefix("payment_obligation.")
        obligation = next(
            (item for item in journey.payment_obligations.all() if str(item.pk) == wanted),
            None,
        )
        return obligation.due_at if obligation is not None else None
    if key.startswith("form_request."):
        wanted = key.removeprefix("form_request.")
        request = next((item for item in journey.form_requests.all() if str(item.pk) == wanted), None)
        return request.due_at if request is not None else None
    return None


def _serialize_intervention(journey, check):
    action = check.next_action
    key_material = f"{journey.pk}:{check.key}:{action.key if action else check.reason_code}"
    item = {
        "key": hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:32],
        "state": check.reason_code,
        "title": action.label if action is not None else check.summary,
        "timing": {},
        "capabilities": [],
        "links": {},
    }
    due_at = _readiness_deadline(journey, check)
    if due_at is not None:
        item["timing"] = {"due_at": _iso(due_at)}
    return item


def _day_of_link(occurrence):
    if occurrence is None:
        return None
    return f"/api/v1/me/occurrences/{occurrence.pk}/day-of/"


def _journey_ongoing_item(journey, readiness):
    summary = {
        ReadinessStatus.BLOCKED: "Quelque chose empêche la suite.",
        ReadinessStatus.ACTION_REQUIRED: "Une action de votre part permet d’avancer.",
        ReadinessStatus.WAITING: "Vous avez fait votre part. Ça suit son cours.",
    }.get(readiness.status, "Cette démarche continue.")
    ready = [
        {
            "kind": check.source,
            "state": check.reason_code,
            "title": check.summary,
        }
        for check in readiness.checks
        if check.state == ReadinessCheckState.SATISFIED
        and check.reason_code in _MEANINGFUL_READY_REASONS
    ]
    if readiness.status == ReadinessStatus.READY and ready:
        summary = "Tout est prêt pour la suite."

    actor_interventions = [
        _serialize_intervention(journey, check)
        for check in readiness.action_items
    ]

    waiting = readiness.waiting_items
    continuation = None
    if waiting:
        continuation = {
            "state": "waiting",
            "summary": waiting[0].summary or summary,
        }

    blocker = None
    if readiness.blocking_items:
        first = readiness.blocking_items[0]
        blocker = {
            "state": first.reason_code,
            "title": first.summary,
            "summary": None,
        }

    next_item = None
    if readiness.next_action is not None:
        source_check = next(
            (check for check in readiness.action_items if check.next_action == readiness.next_action),
            None,
        )
        next_item = {
            "state": source_check.reason_code if source_check is not None else "action_required",
            "title": readiness.next_action.label,
            "timing": {},
        }
        if source_check is not None:
            due_at = _readiness_deadline(journey, source_check)
            if due_at is not None:
                next_item["timing"] = {"due_at": _iso(due_at)}

    return {
        "kind": "journey",
        "source": {"kind": "journey", "id": str(journey.pk)},
        "state": readiness.status.value,
        "title": journey.activity.title,
        "summary": summary,
        "ready": ready,
        "actor_interventions": actor_interventions,
        "continuation": continuation,
        "blocker": blocker,
        "next": next_item,
        "occurrence": (
            {"kind": "occurrence", "id": str(journey.occurrence_id)}
            if journey.occurrence_id
            else None
        ),
        "timing": _occurrence_timing(journey.occurrence),
        "place": _occurrence_place(journey.occurrence),
        "capabilities": ["open_detail"] + (["open_day_of"] if journey.occurrence_id else []),
        "links": {
            "detail": f"/api/v1/me/journeys/{journey.pk}/",
            "web": reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}),
            **(
                {"day_of": _day_of_link(journey.occurrence)}
                if journey.occurrence_id
                else {}
            ),
        },
    }


def _access_ongoing_item(access):
    return {
        "kind": "access",
        "source": {"kind": "access", "id": str(access.pk)},
        "state": "available",
        "title": access.activity.title,
        "summary": "Votre accès est déjà disponible.",
        "ready": [{"kind": "access", "state": "available", "title": "Accès disponible"}],
        "actor_interventions": [],
        "continuation": None,
        "blocker": None,
        "next": None,
        "occurrence": (
            {"kind": "occurrence", "id": str(access.occurrence_id)}
            if access.occurrence_id
            else None
        ),
        "timing": _occurrence_timing(access.occurrence),
        "place": _occurrence_place(access.occurrence),
        "capabilities": ["open_access"] + (["open_day_of"] if access.occurrence_id else []),
        "links": {
            "detail": f"/api/v1/me/accesses/{access.pk}/",
            "web": reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
            **(
                {"day_of": _day_of_link(access.occurrence)}
                if access.occurrence_id
                else {}
            ),
        },
    }


def _dossier_ongoing_item(dossier, *, readiness):
    state = readiness.status.value if readiness.status is not None else dossier.lifecycle

    interventions = []
    if readiness.primary_next_action is not None:
        action = readiness.primary_next_action
        material = f"{dossier.pk}:{action.journey_id}:{action.key or action.reason_code}"
        interventions.append(
            {
                "key": hashlib.sha256(material.encode("utf-8")).hexdigest()[:32],
                "state": action.reason_code or "action_required",
                "title": action.label,
                "timing": {},
                "capabilities": [],
                "links": {},
            }
        )

    blocker = None
    if readiness.status == ReadinessStatus.BLOCKED:
        if readiness.hidden_signal:
            blocker = {
                "state": "blocked",
                "title": readiness.hidden_signal,
                "summary": None,
            }
        else:
            visible = next(
                (item for item in readiness.visible_items if item.status == ReadinessStatus.BLOCKED),
                None,
            )
            blocker = {
                "state": "blocked",
                "title": visible.label if visible is not None else "Blocage",
                "summary": None,
            }

    continuation = None
    if readiness.status == ReadinessStatus.WAITING:
        continuation = {"state": "waiting", "summary": None}

    timing = {}
    if dossier.deadline is not None:
        timing["deadline_date"] = _date(dossier.deadline)

    return {
        "kind": "dossier",
        "source": {"kind": "dossier", "id": str(dossier.pk)},
        "state": state,
        "title": dossier.title,
        "summary": "Cet objectif composé continue.",
        "ready": [],
        "actor_interventions": interventions,
        "continuation": continuation,
        "blocker": blocker,
        "next": None,
        "timing": timing,
        "place": None,
        "capabilities": ["open_detail"],
        "links": {
            "detail": reverse(
                "objectives_api:dossier-detail",
                kwargs={"pk": dossier.pk},
            ),
            "web": reverse(
                "objectives:dossier-detail",
                kwargs={"dossier_id": dossier.pk},
            ),
        },
    }


def _project_ongoing_item(project):
    timing = {}
    if project.starts_on is not None:
        timing["starts_on"] = _date(project.starts_on)
    if project.ends_on is not None:
        timing["ends_on"] = _date(project.ends_on)
    return {
        "kind": "project",
        "source": {"kind": "project", "id": str(project.pk)},
        "state": project.lifecycle,
        "title": project.title,
        "summary": "Cet horizon durable est toujours actif.",
        "ready": [],
        "actor_interventions": [],
        "continuation": None,
        "blocker": None,
        "next": None,
        "timing": timing,
        "place": None,
        "capabilities": ["open_detail"],
        "links": {
            "detail": reverse(
                "objectives_api:project-detail",
                kwargs={"pk": project.pk},
            ),
            "web": reverse(
                "objectives:project-detail",
                kwargs={"project_id": project.pk},
            ),
        },
    }


def _waitlist_ongoing_item(entry):
    offered = entry.status == WaitlistStatus.OFFERED and entry.is_offer_active
    interventions = []
    capabilities = []
    links = {
        "detail": reverse("ticket-waitlist-detail", kwargs={"pk": entry.pk}),
        "web": reverse("tickets:waitlist-list"),
    }
    if offered:
        capabilities = ["accept", "leave"]
        links.update(
            {
                "accept": reverse("ticket-waitlist-accept", kwargs={"pk": entry.pk}),
                "leave": reverse("ticket-waitlist-leave", kwargs={"pk": entry.pk}),
            }
        )
        material = f"waitlist:{entry.pk}:decision"
        interventions.append(
            {
                "key": hashlib.sha256(material.encode("utf-8")).hexdigest()[:32],
                "state": "offer_requires_decision",
                "title": "Répondre à l’offre",
                "timing": {"expires_at": _iso(entry.offer_expires_at)} if entry.offer_expires_at else {},
                "capabilities": capabilities,
                "links": links,
            }
        )
    continuation = None if offered else {"state": "waiting", "summary": None}
    return {
        "kind": "waitlist",
        "source": {"kind": "waitlist", "id": str(entry.pk)},
        "state": "offered" if offered else "waiting",
        "title": entry.ticket_type.event.title,
        "summary": (
            "Une place vous est proposée."
            if offered
            else "Vous attendez qu’une place se libère."
        ),
        "ready": [],
        "actor_interventions": interventions,
        "continuation": continuation,
        "blocker": None,
        "next": None,
        "timing": {"offer_expires_at": _iso(entry.offer_expires_at)} if entry.offer_expires_at else {},
        "place": None,
        "capabilities": capabilities,
        "links": links,
    }


def _transfer_ongoing_item(transfer, *, profile):
    incoming = transfer.recipient_id == profile.pk
    links = {
        "detail": reverse("ticket-transfers-detail", kwargs={"pk": transfer.pk}),
        "web": reverse("tickets:transfer-list"),
    }
    interventions = []
    capabilities = []
    continuation = {"state": "waiting", "summary": None}
    if incoming:
        capabilities = ["accept", "decline"]
        links.update(
            {
                "accept": reverse("ticket-transfers-accept", kwargs={"pk": transfer.pk}),
                "decline": reverse("ticket-transfers-decline", kwargs={"pk": transfer.pk}),
            }
        )
        material = f"transfer:{transfer.pk}:recipient_decision"
        interventions.append(
            {
                "key": hashlib.sha256(material.encode("utf-8")).hexdigest()[:32],
                "state": "recipient_decision_required",
                "title": "Accepter ou refuser",
                "timing": {"expires_at": _iso(transfer.expires_at)},
                "capabilities": capabilities,
                "links": links,
            }
        )
        continuation = None
    else:
        capabilities = ["cancel"]
        links["cancel"] = reverse("ticket-transfers-cancel", kwargs={"pk": transfer.pk})
    return {
        "kind": "transfer",
        "source": {"kind": "ticket_transfer", "id": str(transfer.pk)},
        "state": "pending",
        "title": transfer.ticket.event.title,
        "summary": (
            "Un transfert attend votre décision."
            if incoming
            else "Votre transfert attend la réponse du destinataire."
        ),
        "ready": [],
        "actor_interventions": interventions,
        "continuation": continuation,
        "blocker": None,
        "next": None,
        "timing": {"expires_at": _iso(transfer.expires_at)},
        "place": None,
        "capabilities": capabilities,
        "links": links,
    }


def _payment_ongoing_item(payment):
    return {
        "kind": "payment",
        "source": {"kind": "payment", "id": str(payment.pk)},
        "state": payment.status,
        "title": "Paiement en cours",
        "summary": f"{payment.amount} {payment.currency} · {payment.get_status_display()}",
        "ready": [],
        "actor_interventions": [],
        "continuation": {"state": "waiting", "summary": None},
        "blocker": None,
        "next": None,
        "timing": {},
        "place": None,
        "capabilities": [],
        "links": {
            "detail": reverse("payment-detail", kwargs={"pk": payment.pk}),
            "web": reverse("payments:detail", kwargs={"pk": payment.pk}),
        },
    }


def _funding_ongoing_item(funding):
    activity = funding.activity
    return {
        "kind": "funding",
        "source": {"kind": "activity", "id": str(activity.pk)},
        "state": activity.status,
        "title": activity.title,
        "summary": (
            f"Financement {activity.get_status_display().lower()}"
            + (
                f" · objectif {funding.target_amount} {funding.currency}"
                if funding.target_amount
                else ""
            )
        ),
        "ready": [],
        "actor_interventions": [],
        "continuation": {"state": "active", "summary": None},
        "blocker": None,
        "next": None,
        "timing": {},
        "place": None,
        "capabilities": ["open_detail"],
        "links": {
            "detail": reverse("funding:manage", kwargs={"pk": funding.pk}),
        },
    }


def _ongoing_identity(item):
    source = item["source"]
    material = f'{source["kind"]}:{source["id"]}'
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _decorate_ongoing_semantics(item, *, observed_at):
    """Add Mature continuity semantics without becoming an owner domain."""

    identity = _ongoing_identity(item)
    source = item["source"]
    continuation = item.get("continuation")
    blocker = item.get("blocker")
    next_item = item.get("next")
    links = item.get("links", {})
    settled = list(item.get("ready", []))
    my_side = list(item.get("actor_interventions", []))
    elsewhere = [continuation] if continuation is not None else []
    makolo = []
    item.update(
        {
            "id": identity,
            "continuity_identity": identity,
            "continuity_basis": [source],
            "human_context": item["title"],
            "synthesis": item["summary"],
            # C0 human aliases remain available beside the structured Mature
            # dimensions during the supported-client transition.
            "where_i_am": item["summary"],
            "profile_side_remaining": [
                value
                for value in (
                    entry.get("title") or entry.get("summary")
                    for entry in my_side
                )
                if value
            ],
            "continues_elsewhere": [
                value
                for value in (
                    entry.get("summary") or entry.get("title")
                    for entry in elsewhere
                )
                if value
            ],
            "makolo_preparation": None,
            "settled": settled,
            "my_side": my_side,
            "elsewhere": elsewhere,
            # These remain empty until an owner establishes the corresponding
            # facts; En cours must not invent Makolo or system activity.
            "makolo": makolo,
            "system_or_time": [],
            "next_items": [next_item] if next_item is not None else [],
            "blockers": (
                [
                    {
                        "source": source,
                        "blocked_transition": blocker,
                        "horizon": None,
                        "alternatives": [],
                    }
                ]
                if blocker is not None
                else []
            ),
            "outcome": None,
            "knowledge_context": {
                "provenance": [source],
                "freshness": {
                    "state": "fresh",
                    "observed_at": _iso(observed_at),
                },
                "knowledge_state": "known",
            },
            "relation_projections": [],
            "temporal_facts": [],
            "actions": list(item.get("actor_interventions", [])),
            "media_bindings": [],
            "owner_depth": {
                "source": source,
                "links": {
                    key: value
                    for key, value in links.items()
                    if key in {"detail", "web", "day_of"}
                },
            },
            "handoffs": [
                {
                    "type": "owner",
                    "target": source["kind"],
                    "id": source["id"],
                }
            ],
        }
    )


def ongoing_continuation_offset(token):
    if not token:
        return 0
    payload = signing.loads(
        token,
        salt=ONGOING_CONTINUATION_SALT,
        max_age=60 * 60 * 24,
    )
    offset = int(payload["offset"])
    if offset < 0:
        raise ValueError("Invalid continuation offset.")
    return offset


def build_personal_ongoing_projection(
    profile,
    *,
    observed_at=None,
    continuation_offset=0,
):
    """Serialize the shared bounded En cours read model for API/mobile."""

    observed_at = observed_at or timezone.now()
    entries = build_personal_ongoing_read_model(
        profile,
        observed_at=observed_at,
        limit=continuation_offset + ONGOING_LIMIT + 1,
        include_personal_funding=True,
    )
    entries = pass_ongoing_candidates_through_molongo(entries)
    entries = entries[
        continuation_offset : continuation_offset + ONGOING_LIMIT + 1
    ]
    has_more = len(entries) > ONGOING_LIMIT
    entries = entries[:ONGOING_LIMIT]
    items = []
    for entry in entries:
        if entry.kind == "journey":
            items.append(_journey_ongoing_item(entry.value, entry.readiness))
        elif entry.kind == "access":
            items.append(_access_ongoing_item(entry.value))
        elif entry.kind == "dossier":
            items.append(
                _dossier_ongoing_item(
                    entry.value,
                    readiness=entry.readiness,
                )
            )
        elif entry.kind == "project":
            items.append(_project_ongoing_item(entry.value))
        elif entry.kind == "waitlist":
            items.append(_waitlist_ongoing_item(entry.value))
        elif entry.kind == "transfer":
            items.append(_transfer_ongoing_item(entry.value, profile=profile))
        elif entry.kind == "payment":
            items.append(_payment_ongoing_item(entry.value))
        elif entry.kind == "funding":
            items.append(_funding_ongoing_item(entry.value))

    for item in items:
        _decorate_ongoing_semantics(item, observed_at=observed_at)

    is_empty = not items
    profile_id = str(profile.pk)
    return {
        "surface": "ongoing_me",
        "actor": {"type": "profile", "id": profile_id},
        "viewer": {"type": "profile", "id": profile_id},
        "freshness": {
            "state": "fresh",
            "observed_at": _iso(observed_at),
        },
        "selection": {
            "state": "empty" if is_empty else "ready",
            "reason": "no_personal_continuity" if is_empty else None,
        },
        "capabilities": [],
        "handoffs": [],
        "links": {
            "accesses": reverse("personal-projections:accesses"),
            "history": reverse("personal-projections:history"),
        },
        "items": items,
        "coverage_state": "partial" if has_more else "complete",
        "continuation": {
            "state": "more" if has_more else "end",
            "token": (
                signing.dumps(
                    {"offset": continuation_offset + ONGOING_LIMIT},
                    salt=ONGOING_CONTINUATION_SALT,
                    compress=True,
                )
                if has_more
                else None
            ),
        },
        "terminal": {
            "state": "empty" if is_empty else "ok",
            "message": None,
        },
    }

from __future__ import annotations

import hashlib
from datetime import date, datetime
from zoneinfo import ZoneInfo

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

from core.api.now_composition_projection import dossier_dependency_now_situations
from core.home_presentation import resolve_mature_home_contextual_actions
from core.participant_selectors import participant_active_accesses, participant_active_journeys
from core.personal_surface_orchestration import (
    pass_now_candidates_through_molongo,
    pass_ongoing_candidates_through_molongo,
)
from core.read_models import build_personal_ongoing_read_model


NOW_LIMIT = 12
NOW_CONTINUATION_SALT = "makolo.personal.now.v1"

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

    # S4 is admitted only for an owner Readiness check whose waiting
    # consequence is CURRENT (due or overdue). Routine waiting belongs in
    # En cours and must never populate Now just to fill its root.
    if (
        action.actionability == ContextualActionability.WAITING
        and action.kind == "readiness.waiting"
        and action.identity.context_type == "journey"
        and action.deadline_state in {
            ContextualDeadlineState.OVERDUE,
            ContextualDeadlineState.DUE_TODAY,
        }
    ):
        return "waiting"

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
    if dimension == "waiting":
        return "wait"
    if dimension == "decision":
        return "decide"
    if dimension == "adaptation":
        return "understand"
    return "act"


_NOW_CAPABILITY_LABELS = {
    "accept": "Accepter",
    "decline": "Refuser",
    "leave": "Laisser passer",
    "acknowledge": "Confirmer la lecture",
    "respond": "Répondre",
}

def _now_business_action_payloads(action: ContextualAction, item: dict) -> list[dict]:
    """Interpret existing owner links; Presentation never grants authority."""
    owner = item["source"]
    links = item["links"]
    result = []
    for capability in item["capabilities"]:
        if capability not in links:
            continue
        # Only a precisely scoped Profile recognition decision has a
        # supported bearer-authenticated one-step owner mutation. All other
        # operations remain focused owner handoffs.
        direct = (
            (
                owner["kind"] == "recognition_redemption"
                and action.kind == "recognition.beneficiary_decision"
                and capability in {"accept", "decline"}
            )
            or (
                owner["kind"] == "waitlist"
                and action.kind == "waitlist.offer_decision"
                and capability in {"accept", "leave"}
            )
            or (
                owner["kind"] == "ticket_transfer"
                and action.kind == "transfer.recipient_decision"
                and capability in {"accept", "decline"}
            )
        )
        result.append({
            "capability": capability,
            "label": _NOW_CAPABILITY_LABELS.get(capability, action.label),
            "href": links[capability],
            "interaction_depth": "direct_now" if direct else "focused",
            "confirmation_required": direct,
        })
    return result


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
            "turn": {"type": "none" if dimension in {"adaptation", "waiting"} else "profile"},
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
                    # The projection timestamp does not establish owner-data freshness.
                    "state": "unknown",
                    "observed_at": _iso(observed_at),
                },
                "knowledge_state": "known",
            },
            "attention": {
                "level": "near" if dimension == "adaptation" else "foreground",
            },
            "business_actions": _now_business_action_payloads(action, item),
            "handoffs": [
                {
                    "type": "owner",
                    "target": source["kind"],
                    "id": source["id"],
                }
            ],
        }
    )


def now_continuation_offset(token, *, profile):
    """Return the next owner-scoped page; a token never selects the actor."""
    if not token:
        return 0
    payload = signing.loads(
        token,
        salt=NOW_CONTINUATION_SALT,
        max_age=60 * 60,
    )
    if not isinstance(payload, dict) or payload.get("viewer") != str(profile.pk):
        raise ValueError("Continuation belongs to another viewer.")
    offset = payload.get("offset")
    if type(offset) is not int or offset < NOW_LIMIT or offset % NOW_LIMIT:
        raise ValueError("Invalid Now continuation offset.")
    return offset


def build_personal_now_projection(profile, *, observed_at=None, continuation_offset=0):
    observed_at = observed_at or timezone.now()
    result, metadata = resolve_mature_home_contextual_actions(
        profile,
        observed_at=observed_at,
        include_prepared_start=False,
    )
    actions = pass_now_candidates_through_molongo(result.actions)
    # Current owner-backed waiting must not compete with an intervention
    # already emitted by the same owner. Keep its calm S4 presence bounded.
    active_sources = {
        (source["kind"], source["id"])
        for action in actions
        if (dimension := _now_dimension(action)) is not None
        and dimension != "waiting"
        if (source := _source_for_action(action)) is not None
    }
    waiting_sources = set()
    items = []
    for action in actions:
        dimension = _now_dimension(action)
        if dimension is None:
            continue
        if dimension == "waiting":
            source = _source_for_action(action)
            if source is None:
                continue
            key = (source["kind"], source["id"])
            if (
                key in active_sources
                or key in waiting_sources
                or len(waiting_sources) >= 3
            ):
                continue
            waiting_sources.add(key)
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
    occurrence_by_journey = {}
    if journey_ids:
        occurrence_by_journey = {
            str(pk): occurrence_id
            for pk, occurrence_id in Journey.objects.filter(
                pk__in=journey_ids,
                beneficiary=profile,
            ).values_list("pk", "occurrence_id")
            if occurrence_id is not None
        }
    # Public recognition media is owned by Presentation and bound to an
    # eligible Activity. It must not reveal private Journey attachments.
    public_recognition_by_journey = {}
    if journey_ids:
        from accounts.models import UserProfile
        from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence
        from groups.selectors import eligible_activity_ids_for_profile
        from organizations.models import SpaceLifecycle
        from presentations.media_selectors import public_presentation_media_for_activities

        linked = {
            str(pk): activity_id
            for pk, activity_id in Journey.objects.filter(
                pk__in=journey_ids, beneficiary=profile
            ).values_list("pk", "activity_id")
            if activity_id is not None
        }
        candidates = list(Activity.objects.filter(
            pk__in=set(linked.values()),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        ).select_related("space"))
        eligible = set(eligible_activity_ids_for_profile(profile, [a.pk for a in candidates]))
        public_owners = set(UserProfile.objects.filter(
            user_id__in=[a.owner_profile_id for a in candidates if a.owner_profile_id],
            public_profile=True, searchable=True, user__is_active=True,
        ).values_list("user_id", flat=True))
        allowed = [
            a for a in candidates
            if a.pk in eligible and (
                (
                    a.space_id is not None
                    and a.space.public_profile
                    and a.space.searchable
                    and a.space.lifecycle == SpaceLifecycle.ACTIVE
                    and a.space.verification_status != "suspended"
                ) or (a.space_id is None and a.owner_profile_id in public_owners)
            )
        ]
        if allowed:
            occurrence_ids = set(occurrence_by_journey.values())
            occurrences = Occurrence.objects.filter(
                pk__in=occurrence_ids,
                activity_id__in=[activity.pk for activity in allowed],
            )
            public_media = public_presentation_media_for_activities(
                allowed, occurrences=occurrences,
            )
            for journey_id, activity_id in linked.items():
                occurrence_id = occurrence_by_journey.get(journey_id)
                images = [
                    media for media in public_media.get(str(activity_id), [])
                    if (media.occurrence_id is None or
                        media.occurrence_id == str(occurrence_id))
                    and media.mime_type in {"image/jpeg", "image/png"}
                ]
                images.sort(key=lambda media: (
                    media.occurrence_id != str(occurrence_id),
                    media.position,
                    media.use_id,
                ))
                if images:
                    media = images[0]
                    public_recognition_by_journey[journey_id] = {
                        "resource_ref": f"presentation_media_use:{media.use_id}",
                        "target": "subject",
                        "purpose": "recognize",
                        "kind": "image",
                        "mime_type": media.mime_type,
                        "label": media.alt_text,
                        "url": reverse("presentations:published-media-file",
                                       kwargs={"use_id": media.use_id}),
                        "authorized": True,
                        "presentation_rank": "primary",
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
        media = artifact_media_by_journey.get(journey_id) or []
        recognition = public_recognition_by_journey.get(journey_id)
        if recognition or media:
            item["media_bindings"] = (
                ([recognition] if recognition else []) + list(media)
            )

    serialized_items = [item for _, item in items]
    for composed in dossier_dependency_now_situations(profile, observed_at=observed_at):
        # Upgrade an already displayed generic Dossier blocker when the
        # owner's exact visible dependency explains it more precisely. Never
        # replace an action or the privacy-safe hidden-influence signal.
        replace_at = next(
            (
                i
                for i, existing in enumerate(serialized_items)
                if existing["source"] == composed["source"]
                and existing.get("dimension") == "adaptation"
                and existing.get("kind") != "dossier.hidden_influence"
                and not existing.get("business_actions")
            ),
            None,
        )
        if replace_at is None:
            serialized_items.append(composed)
        else:
            serialized_items[replace_at] = composed
    # Page only after owner admission, permissions and composition.
    if type(continuation_offset) is not int or continuation_offset < 0:
        raise ValueError("Invalid Now continuation offset.")
    is_empty = not serialized_items
    page = serialized_items[continuation_offset : continuation_offset + NOW_LIMIT + 1]
    has_more = len(page) > NOW_LIMIT
    page = page[:NOW_LIMIT]
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
        "items": page,
        "coverage_state": "partial" if has_more else "complete",
        "continuation": (
            None if is_empty else {
                "state": "more" if has_more else "end",
                "token": (
                    signing.dumps(
                        {"viewer": profile_id, "offset": continuation_offset + NOW_LIMIT},
                        salt=NOW_CONTINUATION_SALT,
                        compress=True,
                    ) if has_more else None
                ),
            }
        ),
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


def _access_ongoing_item(access, *, profile):
    # Access is a different owner, but can continue the same personal Journey.
    # Never carry this identity across a transfer to another beneficiary.
    journey = access.journey if access.journey_id else None
    ticket = getattr(access, "ticket", None)
    order = ticket.order if ticket is not None else None
    waitlist = getattr(order, "waitlist_entry", None) if order is not None else None
    waitlist_anchor = (
        {"kind": "waitlist", "id": str(waitlist.pk)}
        if waitlist is not None and waitlist.user_id == profile.pk
        else None
    )
    journey_anchor = (
        {"kind": "journey", "id": str(journey.pk)}
        if journey is not None and journey.beneficiary_id == profile.pk
        else None
    )
    anchor = waitlist_anchor or journey_anchor
    return {
        "continuity_identity_anchor": anchor,
        "continuity_related_basis": [
            basis for basis in (waitlist_anchor, journey_anchor) if basis is not None
        ],
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
        "access_window": {
            "valid_from": _iso(access.valid_from) if access.valid_from else None,
            "valid_until": _iso(access.valid_until) if access.valid_until else None,
        },
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
    source = item.get("continuity_identity_anchor") or item["source"]
    material = f'{source["kind"]}:{source["id"]}'
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _ongoing_n1_when(timing):
    """Humanized owner date, never an internal timestamp."""
    raw = timing.get("start_at") or timing.get("start_date") or timing.get("deadline_date")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        if "T" in raw or " " in raw:
            instant = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            zone = timing.get("timezone")
            if zone and instant.tzinfo is not None:
                instant = instant.astimezone(ZoneInfo(zone))
            return instant.strftime("%d/%m/%Y · %H:%M")
        return date.fromisoformat(raw).strftime("%d/%m/%Y")
    except (TypeError, ValueError, OverflowError, KeyError):
        return None


def _ongoing_n1(item):
    """A small, additive display projection shared by Web and mobile."""
    blocker = item.get("blocker")
    interventions = item.get("actor_interventions") or []
    continuation = item.get("continuation") or {}
    if blocker:
        cue, tone = "Une étape bloquée", "attention"
    elif interventions:
        cue, tone = "De votre côté", "action"
    elif continuation.get("state") == "waiting":
        cue, tone = "En attente", "calm"
    elif item.get("state") == "available":
        cue, tone = "Accès disponible", "ready"
    else:
        cue, tone = None, "calm"
    title = item.get("title") or ""
    summary = item.get("summary") or ""
    next_item = item.get("next") or {}
    supporting = next_item.get("title")
    if supporting and supporting.strip().casefold() in {
        title.strip().casefold(), summary.strip().casefold()
    }:
        supporting = None
    place = item.get("place") or {}
    return {
        "cue": cue,
        "tone": tone,
        "supporting": supporting,
        "when_label": _ongoing_n1_when(item.get("timing") or {}),
        "place_label": place.get("name") or place.get("locality"),
    }


def _attach_ongoing_recognition_media(entries, items, *, viewer):
    """Batch resolve published media against the same authorization as delivery."""
    from accounts.models import UserProfile
    from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence
    from groups.selectors import eligible_activity_ids_for_profile
    from organizations.models import SpaceLifecycle
    from presentations.media_selectors import public_presentation_media_for_activities
    from tickets.models import Ticket, TicketType
    from discovery.models import ActivityBookmark
    from discovery.search import public_occurrences_for_activities
    from groups.selectors import filter_queryset_by_activity_group_eligibility

    # Ticket offers and transfers are personal pursuits of Event Activities.
    # Resolve their owner links in batches rather than per displayed row.
    type_ids = {
        entry.value.ticket_type_id
        for entry in entries if entry.kind == "waitlist"
    }
    ticket_ids = {
        entry.value.ticket_id
        for entry in entries if entry.kind == "transfer"
    }
    type_activities = {
        str(ticket_type.pk): ticket_type.event.activity_id
        for ticket_type in TicketType.objects.filter(
            pk__in=type_ids
        ).select_related("event")
    } if type_ids else {}
    ticket_activities = {
        str(ticket.pk): ticket.event.activity_id
        for ticket in Ticket.objects.filter(
            pk__in=ticket_ids
        ).select_related("event")
    } if ticket_ids else {}

    references = []
    activity_ids = set()
    occurrence_ids = set()
    for entry in entries:
        if entry.kind == "waitlist":
            activity_id = type_activities.get(str(entry.value.ticket_type_id))
            occurrence_id = None
        elif entry.kind == "transfer":
            activity_id = ticket_activities.get(str(entry.value.ticket_id))
            occurrence_id = None
        elif entry.kind in {"journey", "access", "funding"}:
            activity_id = getattr(entry.value, "activity_id", None)
            occurrence_id = getattr(entry.value, "occurrence_id", None)
        else:
            references.append((None, None))
            continue
        references.append((str(activity_id) if activity_id else None,
                           str(occurrence_id) if occurrence_id else None))
        if activity_id:
            activity_ids.add(activity_id)
        if occurrence_id:
            occurrence_ids.add(occurrence_id)
    if not activity_ids:
        return

    activities = list(
        Activity.objects.filter(
            pk__in=activity_ids,
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        ).select_related("space")
    )
    group_eligible = set(
        eligible_activity_ids_for_profile(viewer, [a.pk for a in activities])
    )
    public_profiles = set(
        UserProfile.objects.filter(
            user_id__in=[a.owner_profile_id for a in activities if a.owner_profile_id],
            public_profile=True, searchable=True, user__is_active=True,
        ).values_list("user_id", flat=True)
    )
    allowed = [
        a for a in activities
        if a.pk in group_eligible and (
            (
                a.space_id is not None
                and a.space.public_profile and a.space.searchable
                and a.space.lifecycle == SpaceLifecycle.ACTIVE
                and a.space.verification_status != "suspended"
            ) or (
                a.space_id is None and a.owner_profile_id in public_profiles
            )
        )
    ]
    if not allowed:
        return
    occurrences = Occurrence.objects.filter(
        pk__in=occurrence_ids, activity_id__in=[a.pk for a in allowed]
    )
    media_by_activity = public_presentation_media_for_activities(
        allowed, occurrences=occurrences
    )
    # Share Discovery's published PUBLIC resources; private owner documents
    # must use their own authorized endpoints and are never inferred here.
    from discovery.api.composition import _activity_resource_previews
    resources_by_activity = _activity_resource_previews([a.pk for a in allowed])
    # Reuse Discovery's public admission, not just a published Activity flag.
    # An Ongoing entry never transfers authority to share or save its owner.
    discoverable = {
        str(occurrence.activity_id)
        for occurrence in filter_queryset_by_activity_group_eligibility(
            public_occurrences_for_activities([a.pk for a in allowed]),
            viewer,
        )
    }
    family_by_activity = {activity_id: "activity" for activity_id in discoverable}
    allowed_ids = {str(activity.pk) for activity in allowed}
    # Some canonical services and fundings have no public Occurrence. They
    # still exist in Discovery, but only its own selector may admit them.
    from discovery.api.composition import detail_candidate
    for entry, (activity_id, _) in zip(entries, references):
        if not activity_id or activity_id not in allowed_ids:
            continue
        if activity_id in family_by_activity:
            continue
        if entry.kind == "funding":
            candidates = ("funding_activity",)
        elif entry.kind in {"journey", "access"}:
            candidates = ("service_activity",)
        else:
            continue
        for family in candidates:
            if detail_candidate(family, activity_id, profile=viewer) is not None:
                family_by_activity[activity_id] = family
                break
    saved_ids = {
        str(activity_id)
        for activity_id in ActivityBookmark.objects.filter(
            user=viewer, activity_id__in=family_by_activity.keys()
        ).values_list("activity_id", flat=True)
    }
    for item, (activity_id, occurrence_id) in zip(items, references):
        if not activity_id:
            continue
        admissible = [
            media for media in media_by_activity.get(activity_id, [])
            if media.occurrence_id is None or media.occurrence_id == occurrence_id
        ]
        admissible.sort(key=lambda media: (
            media.occurrence_id != occurrence_id, media.position, media.use_id
        ))
        family = family_by_activity.get(activity_id)
        if family:
            # Mutation and Sharing independently reauthorize this family at
            # execution time. A presentation reference is never a mandate.
            saved = activity_id in saved_ids
            item["n1"]["possibility"] = {
                "family": family,
                "id": activity_id,
                "saved_state": "saved" if saved else "not_saved",
                "capabilities": ["unsave" if saved else "save", "share"],
                "links": {
                    "saved": reverse(
                        "discovery_api:item-saved",
                        kwargs={"family": family, "item_id": activity_id},
                    ),
                    "share": reverse(
                        "sharing_api:possibility",
                        kwargs={"family": family, "item_id": activity_id},
                    ),
                },
            }
        item["resources"] = list(resources_by_activity.get(activity_id, []))
        item["media_bindings"] = [
            {
                "resource": {
                    "kind": "presentation_media_use",
                    "id": media.use_id,
                    "url": reverse("presentations:published-media-file",
                                   kwargs={"use_id": media.use_id}),
                    "mime_type": media.mime_type,
                    "alt_text": media.alt_text,
                },
                "target": {"kind": "ongoing_continuity", "id": item["id"]},
                "purpose": "RECOGNIZE",
            }
            for media in admissible[:3]
            if media.mime_type in {"image/jpeg", "image/png"}
        ]


def _ongoing_temporal_facts(item):
    """Owner-established human dates only, never technical timestamps."""
    facts = []
    timing = item.get("timing") or {}
    source = item["source"]
    if timing.get("start_at") or timing.get("start_date"):
        facts.append({
            "kind": "occurrence_start",
            "label": "Début",
            "at": timing.get("start_at"),
            "date": timing.get("start_date"),
            "timezone": timing.get("timezone"),
            "source": item.get("occurrence") or source,
        })
    next_item = item.get("next") or {}
    due_at = (next_item.get("timing") or {}).get("due_at")
    if due_at:
        facts.append({
            "kind": "next_due",
            "label": next_item.get("title") or "Échéance",
            "at": due_at,
            "source": source,
        })
    expires_at = timing.get("offer_expires_at") or timing.get("expires_at")
    if expires_at:
        facts.append({
            "kind": "decision_expires" if timing.get("offer_expires_at") else "expires",
            "label": "Répondre avant" if timing.get("offer_expires_at") else "Expiration",
            "at": expires_at,
            "source": source,
        })
    access_window = item.get("access_window") or {}
    for field, label in (
        ("valid_from", "Accès utilisable dès"),
        ("valid_until", "Accès valable jusqu'au"),
    ):
        if access_window.get(field):
            facts.append({
                "kind": field,
                "label": label,
                "at": access_window[field],
                "source": source,
            })
    seen = {(fact.get("at"), fact.get("date")) for fact in facts}
    for intervention in item.get("actor_interventions") or []:
        window = intervention.get("timing") or {}
        for field in ("due_at", "expires_at"):
            at = window.get(field)
            if not at or (at, None) in seen:
                continue
            facts.append({
                "kind": "intervention_due",
                "label": intervention.get("title") or "Échéance",
                "at": at,
                "source": source,
            })
            seen.add((at, None))
    return facts


def _attach_ongoing_private_journey_resources(items, *, viewer):
    """Project metadata only when the beneficiary may export the artifact.

    No raw file URL, private storage key, QR, or secret enters this read model.
    Export warnings and authorization remain owned by JourneyArtifact.
    """
    from journeys.collaboration_models import JourneyArtifact
    from sharing.document_services import can_export_journey_artifact

    journey_ids = {
        item["source"]["id"]
        for item in items
        if item["source"]["kind"] == "journey"
    }
    if not journey_ids:
        return
    grouped = {}
    for artifact in (
        JourneyArtifact.objects.filter(journey_id__in=journey_ids)
        .select_related("journey")
        .order_by("journey_id", "title", "-version", "id")
    ):
        if not can_export_journey_artifact(viewer, artifact, "download").allowed:
            continue
        grouped.setdefault(str(artifact.journey_id), []).append({
            "kind": "journey_artifact",
            "title": artifact.title,
            "mime_type": artifact.mime_type,
            "description": artifact.get_status_display(),
            "owner": {"kind": "journey", "id": str(artifact.journey_id)},
        })
    for item in items:
        if item["source"]["kind"] == "journey":
            item["resources"].extend(grouped.get(item["source"]["id"], []))


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
            "continuity_basis": [
                *(item.get("continuity_related_basis") or []),
                source,
            ],
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
            "temporal_facts": _ongoing_temporal_facts(item),
            "actions": list(item.get("actor_interventions", [])),
            "media_bindings": [],
            "resources": [],
            "n1": _ongoing_n1(item),
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


def ongoing_continuation_offset(token, *, profile):
    """Decode an opaque, viewer-bound continuation. Never select a Profile."""
    if not token:
        return 0
    payload = signing.loads(
        token,
        salt=ONGOING_CONTINUATION_SALT,
        max_age=60 * 60,
    )
    if not isinstance(payload, dict) or payload.get("viewer") != str(profile.pk):
        raise ValueError("Continuation belongs to another viewer.")
    offset = payload.get("offset")
    if type(offset) is not int or offset < ONGOING_LIMIT or offset % ONGOING_LIMIT:
        raise ValueError("Invalid Ongoing continuation offset.")
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
            items.append(_access_ongoing_item(entry.value, profile=profile))
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

    _attach_ongoing_recognition_media(entries, items, viewer=profile)
    _attach_ongoing_private_journey_resources(items, viewer=profile)

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
                    {"offset": continuation_offset + ONGOING_LIMIT, "viewer": profile_id},
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

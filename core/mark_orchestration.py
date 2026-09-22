from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from urllib.parse import urlencode
from uuid import UUID

from django.urls import reverse

from core.participant_selectors import (
    participant_active_accesses,
    participant_active_journeys,
)


MARK_TEXT_MAX_LENGTH = 600
MARK_CLARIFICATION_LIMIT = 5

_AUTHORITY_CONTEXT_KEYS = {
    "act_as_space",
    "mandate",
    "permission",
    "profile_id",
    "role",
    "space_id",
}

_DISCOVERY_FAMILIES = {
    "activity",
    "service_activity",
    "funding_activity",
    "opportunity",
}


def _fold(value: str) -> str:
    value = " ".join(str(value or "").casefold().split())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _contains(value: str, phrases) -> bool:
    return any(phrase in value for phrase in phrases)


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _selected(context):
    selected = _mapping(context.get("selected"))
    return {
        "kind": str(selected.get("kind") or "").strip(),
        "id": str(selected.get("id") or "").strip(),
        "family": str(selected.get("family") or "").strip(),
    }


def _situation(folded: str) -> str:
    if _contains(
        folded,
        (
            "pourquoi",
            "qu'est-ce que",
            "qu est ce que",
            "ca veut dire",
            "je veux comprendre",
            "je ne sais pas quoi faire",
        ),
    ):
        return "understand"
    if _contains(
        folded,
        (
            "a change",
            "ont change",
            "je suis arrive",
            "j'ai deja paye",
            "j ai deja paye",
            "on m'a refuse",
            "on m a refuse",
            "j'ai recu",
            "j ai recu",
        ),
    ):
        return "changed"
    if _contains(
        folded,
        (
            "j'ai ",
            "j ai ",
            "voici ",
            "ils m'ont envoye",
            "ils m ont envoye",
        ),
    ):
        return "have"
    if _contains(
        folded,
        (
            "je veux",
            "je cherche",
            "trouve",
            "organise",
            "ouvre",
            "continue",
            "garde",
            "previens",
        ),
    ):
        return "want"
    return "unknown"


def _response(
    *,
    state,
    situation,
    intent,
    message,
    result=None,
    question=None,
    action=None,
    handoff=None,
    links=None,
    web=None,
):
    return {
        "state": state,
        "understanding": {
            "situation": situation,
            "intent": intent,
        },
        "result": result,
        "question": question,
        "action": action,
        "handoff": handoff,
        "links": links or {},
        "message": message,
        "_web": web,
    }


def public_mark_result(result):
    return {
        key: value
        for key, value in result.items()
        if not key.startswith("_")
    }


def mark_web_url(result):
    web = _mapping(result.get("_web"))
    route = web.get("route")
    if not route:
        return None
    kwargs = dict(_mapping(web.get("kwargs")))
    url = reverse(route, kwargs=kwargs or None)
    query = _mapping(web.get("query"))
    if query:
        return f"{url}?{urlencode(query)}"
    return url


def _handoff(owner, surface):
    return {
        "owner": owner,
        "surface": surface,
    }


def _clarification(*, situation, intent, code, summary, options=None):
    return _response(
        state="needs_clarification",
        situation=situation,
        intent=intent,
        message=summary,
        question={
            "code": code,
            "summary": summary,
            "options": list(options or [])[:MARK_CLARIFICATION_LIMIT],
        },
    )


def _unknown_target(*, situation, intent):
    return _response(
        state="unknown",
        situation=situation,
        intent=intent,
        message=(
            "Makolo ne retrouve pas cette cible dans les réalités personnelles "
            "actuellement accessibles."
        ),
        result={
            "state": "unknown",
            "reason": "target_not_available",
        },
    )


def _resolve_access(*, profile, situation, context):
    selected = _selected(context)
    raw_id = selected["id"] if selected["kind"] == "access" else context.get("access_id")
    access_id = _uuid(raw_id) if raw_id else None
    queryset = participant_active_accesses(profile)

    if raw_id:
        access = queryset.filter(pk=access_id).first() if access_id else None
        if access is None:
            return _unknown_target(
                situation=situation,
                intent="retrieve_access",
            )
        return _access_result(access, situation=situation)

    rows = list(
        queryset.order_by("occurrence__start_at", "-created_at", "id")[
            : MARK_CLARIFICATION_LIMIT + 1
        ]
    )
    if len(rows) == 1:
        return _access_result(rows[0], situation=situation)
    if len(rows) > 1:
        options = [
            {
                "kind": "access",
                "id": str(row.pk),
                "label": row.activity.title,
                "state": row.status,
                "links": {
                    "detail": reverse(
                        "personal-detail-projections:access-detail",
                        kwargs={"pk": row.pk},
                    )
                },
            }
            for row in rows[:MARK_CLARIFICATION_LIMIT]
        ]
        return _clarification(
            situation=situation,
            intent="retrieve_access",
            code="which_access",
            summary="Plusieurs accès personnels correspondent. Lequel voulez-vous ouvrir ?",
            options=options,
        )

    return _response(
        state="resolved",
        situation=situation,
        intent="retrieve_access",
        message="Aucun accès personnel actif n'est actuellement disponible.",
        result={"kind": "access_collection", "count": 0},
        handoff=_handoff("access", "personal_accesses"),
        links={"collection": reverse("personal-projections:accesses")},
        web={"route": "core:participant-accesses"},
    )


def _access_result(access, *, situation):
    detail = reverse(
        "personal-detail-projections:access-detail",
        kwargs={"pk": access.pk},
    )
    return _response(
        state="resolved",
        situation=situation,
        intent="retrieve_access",
        message=f"Makolo a retrouvé votre accès pour « {access.activity.title} ».",
        result={
            "kind": "access",
            "id": str(access.pk),
            "state": access.status,
            "activity": {
                "kind": "activity",
                "id": str(access.activity_id),
                "title": access.activity.title,
            },
        },
        handoff=_handoff("access", "access_detail"),
        links={"detail": detail},
        web={
            "route": "core:participant-access-detail",
            "kwargs": {"pk": str(access.pk)},
        },
    )


def _resolve_journey(*, profile, situation, context, intent="retrieve_journey"):
    selected = _selected(context)
    raw_id = (
        selected["id"]
        if selected["kind"] == "journey"
        else context.get("journey_id")
    )
    journey_id = _uuid(raw_id) if raw_id else None
    queryset = participant_active_journeys(profile)

    if raw_id:
        journey = queryset.filter(pk=journey_id).first() if journey_id else None
        if journey is None:
            return _unknown_target(
                situation=situation,
                intent=intent,
            )
        return _journey_result(journey, situation=situation, intent=intent)

    rows = list(
        queryset.order_by("-updated_at", "id")[
            : MARK_CLARIFICATION_LIMIT + 1
        ]
    )
    if len(rows) == 1:
        return _journey_result(rows[0], situation=situation, intent=intent)
    if len(rows) > 1:
        options = [
            {
                "kind": "journey",
                "id": str(row.pk),
                "label": row.activity.title,
                "state": row.status,
                "links": {
                    "detail": reverse(
                        "personal-detail-projections:journey-detail",
                        kwargs={"pk": row.pk},
                    )
                },
            }
            for row in rows[:MARK_CLARIFICATION_LIMIT]
        ]
        return _clarification(
            situation=situation,
            intent=intent,
            code="which_journey",
            summary=(
                "Plusieurs démarches personnelles peuvent correspondre. "
                "Laquelle voulez-vous continuer ?"
            ),
            options=options,
        )

    return _response(
        state="resolved",
        situation=situation,
        intent=intent,
        message="Aucune démarche personnelle active ne correspond actuellement.",
        result={"kind": "journey_collection", "count": 0},
        handoff=_handoff("journey", "ongoing"),
        links={"collection": reverse("personal-projections:ongoing")},
        web={"route": "core:participant-ongoing"},
    )


def _journey_result(journey, *, situation, intent):
    detail = reverse(
        "personal-detail-projections:journey-detail",
        kwargs={"pk": journey.pk},
    )
    return _response(
        state="resolved",
        situation=situation,
        intent=intent,
        message=f"Makolo a retrouvé « {journey.activity.title} ».",
        result={
            "kind": "journey",
            "id": str(journey.pk),
            "state": journey.status,
            "activity": {
                "kind": "activity",
                "id": str(journey.activity_id),
                "title": journey.activity.title,
            },
        },
        handoff=_handoff("journey", "journey_detail"),
        links={"detail": detail},
        web={
            "route": "core:participant-journey-detail",
            "kwargs": {"pk": str(journey.pk)},
        },
    )



def _resolve_objective(*, profile, situation, context, kind):
    from objectives.models import DossierLifecycle, ProjectLifecycle
    from objectives.selectors import dossiers_for_profile, projects_for_profile

    selected = _selected(context)
    raw_id = selected["id"] if selected["kind"] == kind else context.get(f"{kind}_id")
    object_id = _uuid(raw_id) if raw_id else None

    if kind == "dossier":
        queryset = dossiers_for_profile(profile).filter(
            owner_profile=profile,
            owning_space__isnull=True,
            lifecycle__in={DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE},
        )
        web_route, web_kwarg = "objectives:dossier-detail", "dossier_id"
        api_prefix, intent, label = "/api/v1/objectives/dossiers/", "retrieve_dossier", "Dossier"
    else:
        queryset = projects_for_profile(profile).filter(
            owner_profile=profile,
            owning_space__isnull=True,
            lifecycle__in={ProjectLifecycle.DRAFT, ProjectLifecycle.ACTIVE},
        )
        web_route, web_kwarg = "objectives:project-detail", "project_id"
        api_prefix, intent, label = "/api/v1/objectives/projects/", "retrieve_project", "Projet"

    if raw_id:
        row = queryset.filter(pk=object_id).first() if object_id else None
        if row is None:
            return _unknown_target(situation=situation, intent=intent)
        rows = [row]
    else:
        rows = list(queryset.order_by("-updated_at", "id")[: MARK_CLARIFICATION_LIMIT + 1])

    if len(rows) == 1:
        row = rows[0]
        detail = f"{api_prefix}{row.pk}/"
        return _response(
            state="resolved",
            situation=situation,
            intent=intent,
            message=f"Makolo a retrouvé votre {label} « {row.title} ».",
            result={"kind": kind, "id": str(row.pk), "state": row.lifecycle, "title": row.title},
            handoff=_handoff("objectives", f"{kind}_detail"),
            links={"detail": detail},
            web={"route": web_route, "kwargs": {web_kwarg: str(row.pk)}},
        )

    if len(rows) > 1:
        return _clarification(
            situation=situation,
            intent=intent,
            code=f"which_{kind}",
            summary=f"Plusieurs {label.lower()}s personnels correspondent. Lequel voulez-vous ouvrir ?",
            options=[
                {
                    "kind": kind,
                    "id": str(row.pk),
                    "label": row.title,
                    "state": row.lifecycle,
                    "links": {"detail": f"{api_prefix}{row.pk}/"},
                }
                for row in rows[:MARK_CLARIFICATION_LIMIT]
            ],
        )

    return _response(
        state="resolved",
        situation=situation,
        intent=intent,
        message=f"Aucun {label.lower()} personnel actif ne correspond actuellement.",
        result={"kind": f"{kind}_collection", "count": 0},
        handoff=_handoff("objectives", "ongoing"),
        links={"collection": reverse("personal-projections:ongoing")},
        web={"route": "core:participant-ongoing"},
    )

def _resolve_live(*, profile, situation, context):
    selected = _selected(context)
    raw_id = (
        selected["id"]
        if selected["kind"] == "occurrence"
        else context.get("occurrence_id")
    )
    occurrence_id = _uuid(raw_id) if raw_id else None
    if not raw_id:
        return _clarification(
            situation=situation,
            intent="inspect_live",
            code="which_occurrence",
            summary=(
                "Makolo a besoin de savoir de quelle occurrence actuelle "
                "vous parlez."
            ),
        )
    if occurrence_id is None:
        return _unknown_target(
            situation=situation,
            intent="inspect_live",
        )

    from activities.models import Occurrence
    from operations.participant_occurrence_live import (
        resolve_participant_occurrence_live,
    )

    occurrence = (
        Occurrence.objects.select_related("activity")
        .filter(pk=occurrence_id)
        .first()
    )
    live = (
        resolve_participant_occurrence_live(
            occurrence=occurrence,
            actor=profile,
        )
        if occurrence is not None
        else None
    )
    if live is None:
        return _unknown_target(
            situation=situation,
            intent="inspect_live",
        )

    day_of = reverse(
        "personal-projections:day-of",
        kwargs={"pk": occurrence.pk},
    )
    links = {"day_of": day_of}
    if live.get("phase") in {"arrival", "live"}:
        links["live"] = f"/api/v1/operations/occurrences/{occurrence.pk}/live/"
    return _response(
        state="resolved",
        situation=situation,
        intent="inspect_live",
        message=f"Makolo a retrouvé la situation actuelle de « {occurrence.activity.title} ».",
        result={
            "kind": "occurrence",
            "id": str(occurrence.pk),
            "phase": live.get("phase"),
        },
        handoff=_handoff("day_of", "occurrence_day_of"),
        links=links,
    )


def _save_discovery(*, profile, situation, context):
    selected = _selected(context)
    if selected["kind"] != "discovery_item":
        return _clarification(
            situation=situation,
            intent="save_discovery_item",
            code="which_possibility",
            summary="Quelle possibilité voulez-vous garder ?",
        )
    family = selected["family"]
    item_id = _uuid(selected["id"])
    if family not in _DISCOVERY_FAMILIES or item_id is None:
        return _unknown_target(
            situation=situation,
            intent="save_discovery_item",
        )

    from discovery.api.composition import set_saved_state

    projection = set_saved_state(
        family,
        item_id,
        profile=profile,
        save=True,
    )
    if projection is None:
        return _unknown_target(
            situation=situation,
            intent="save_discovery_item",
        )

    resource = projection["identity"]["resource"]
    saved = reverse(
        "discovery_api:item-saved",
        kwargs={"family": family, "item_id": item_id},
    )
    return _response(
        state="completed",
        situation=situation,
        intent="save_discovery_item",
        message="Cette possibilité est maintenant gardée dans Makolo.",
        result={
            "effect": "bookmark_saved",
            "resource": resource,
        },
        handoff=_handoff("discovery", "saved_possibility"),
        links={
            "detail": projection["links"]["detail"],
            "saved": saved,
        },
        action={
            "code": "save",
            "capabilities": projection.get("capabilities", []),
        },
        web={"route": "discovery:bookmarks"},
    )


def _watch_criteria(text, context):
    raw_search = context.get("search")
    if isinstance(raw_search, Mapping):
        return dict(raw_search)

    folded = _fold(text)
    prefixes = (
        "continue a chercher",
        "continue de chercher",
        "continues a chercher",
        "continues de chercher",
    )
    remainder = folded
    for prefix in prefixes:
        if prefix in folded:
            remainder = folded.split(prefix, 1)[1].strip(" :,-")
            break
    if not remainder or remainder in {
        "ca",
        "ceci",
        "cela",
        "ce type",
        "ce type de chose",
    }:
        return None
    return {"q": remainder}


def _ensure_watch(*, profile, text, situation, context):
    criteria = _watch_criteria(text, context)
    if not criteria:
        return _clarification(
            situation=situation,
            intent="create_watch",
            code="what_to_watch",
            summary=(
                "Que voulez-vous que Makolo continue à chercher ? "
                "Une recherche ouverte doit rester explicitement définie."
            ),
        )

    from django.core.exceptions import ValidationError

    from discovery.watches import (
        ensure_discovery_watch,
        normalize_watch_criteria,
        suggest_watch_name,
    )

    try:
        normalized = normalize_watch_criteria(criteria)
        watch, created = ensure_discovery_watch(
            owner=profile,
            criteria=normalized,
            name=suggest_watch_name(normalized),
        )
    except ValidationError:
        return _clarification(
            situation=situation,
            intent="create_watch",
            code="watch_criteria",
            summary=(
                "Les critères donnés ne suffisent pas à créer une Veille "
                "exécutable. Précisez ce que Makolo doit continuer à chercher."
            ),
        )

    detail = reverse(
        "discovery_api:watch-detail",
        kwargs={"watch_id": watch.pk},
    )
    effect = "watch_created" if created else "watch_already_active"
    return _response(
        state="completed",
        situation=situation,
        intent="create_watch",
        message=(
            "Makolo continuera cette recherche et restera silencieux tant "
            "qu'aucun changement utile n'est à signaler."
        ),
        result={
            "effect": effect,
            "watch": {
                "kind": "discovery_watch",
                "id": str(watch.pk),
                "name": watch.name,
                "state": watch.status,
            },
        },
        handoff=_handoff("discovery", "watch"),
        links={
            "detail": detail,
            "collection": reverse("discovery_api:watches"),
        },
        web={
            "route": "discovery:watch-detail",
            "kwargs": {"watch_id": str(watch.pk)},
        },
    )



def _redeem_recognition(*, profile, situation, context):
    from django.core.exceptions import ValidationError

    from recognition.economy import redeem_reward
    from recognition.models import RecognitionRedemption
    from recognition.selectors import account_for_profile, active_rewards

    selected = _selected(context)
    raw_id = (
        selected["id"]
        if selected["kind"] in {"recognition_reward", "reward"}
        else context.get("reward_id")
    )
    reward_id = _uuid(raw_id) if raw_id else None
    account = account_for_profile(profile)
    if account is None:
        return _unknown_target(
            situation=situation,
            intent="redeem_recognition",
        )

    rewards = [
        reward
        for reward in active_rewards(owner_account=account)
        if bool(getattr(reward, "recognition_self_eligible", False))
    ]
    if raw_id:
        reward = next((row for row in rewards if row.pk == reward_id), None)
        if reward is None:
            return _unknown_target(
                situation=situation,
                intent="redeem_recognition",
            )
    elif len(rewards) == 1:
        reward = rewards[0]
    elif len(rewards) > 1:
        return _clarification(
            situation=situation,
            intent="redeem_recognition",
            code="which_recognition_reward",
            summary="Quelle récompense disponible voulez-vous utiliser ?",
            options=[
                {
                    "kind": "recognition_reward",
                    "id": str(row.pk),
                    "label": row.name,
                    "links": {
                        "redeem": reverse(
                            "recognition_api:reward-redeem",
                            kwargs={"reward_id": row.pk},
                        )
                    },
                }
                for row in rewards[:MARK_CLARIFICATION_LIMIT]
            ],
        )
    else:
        return _unknown_target(
            situation=situation,
            intent="redeem_recognition",
        )

    confirmation = _mapping(context.get("confirmation"))
    confirmed = (
        confirmation.get("code") == "redeem_recognition"
        and str(confirmation.get("target_id") or "") == str(reward.pk)
    )
    action = {
        "code": "redeem_recognition",
        "summary": f"Utiliser « {reward.name} » pour vous-même ?",
        "target": {"kind": "recognition_reward", "id": str(reward.pk)},
        "owner": "recognition",
        "idempotency_key_required": True,
    }
    if not confirmed:
        return _response(
            state="needs_confirmation",
            situation=situation,
            intent="redeem_recognition",
            message=action["summary"],
            result={"kind": "recognition_reward", "id": str(reward.pk)},
            action=action,
            handoff=_handoff("recognition", "recognition"),
            links={
                "owner_action": reverse(
                    "recognition_api:reward-redeem",
                    kwargs={"reward_id": reward.pk},
                )
            },
        )

    key = str(context.get("idempotency_key") or "").strip()
    if not key:
        return _response(
            state="needs_confirmation",
            situation=situation,
            intent="redeem_recognition",
            message=(
                "La confirmation est comprise, mais une clé d'idempotence "
                "stable est requise avant d'exécuter l'utilisation."
            ),
            result={"kind": "recognition_reward", "id": str(reward.pk)},
            action=action,
            handoff=_handoff("recognition", "recognition"),
            links={
                "owner_action": reverse(
                    "recognition_api:reward-redeem",
                    kwargs={"reward_id": reward.pk},
                )
            },
        )

    existing = (
        RecognitionRedemption.objects.filter(idempotency_key=key)
        .select_related("owner_account")
        .first()
    )
    if existing is not None and existing.owner_account_id != account.pk:
        return _response(
            state="forbidden",
            situation=situation,
            intent="redeem_recognition",
            message="Cette clé d'idempotence n'est pas disponible.",
            result={"state": "forbidden", "reason": "idempotency_key_unavailable"},
        )

    try:
        redemption = redeem_reward(
            owner_account=account,
            reward=reward,
            idempotency_key=key,
            actor_profile=profile,
            beneficiary_profile=profile,
        )
    except ValidationError:
        return _response(
            state="forbidden",
            situation=situation,
            intent="redeem_recognition",
            message=(
                "Recognition n'autorise plus cette utilisation dans l'état actuel."
            ),
            result={"state": "forbidden", "reason": "owner_action_rejected"},
            handoff=_handoff("recognition", "recognition"),
            links={"detail": "/api/v1/recognition/me/"},
        )

    return _response(
        state="completed",
        situation=situation,
        intent="redeem_recognition",
        message="La récompense a été utilisée par le service Recognition.",
        result={
            "effect": "recognition_redeemed",
            "redemption": {
                "kind": "recognition_redemption",
                "id": str(redemption.pk),
                "state": redemption.status,
            },
        },
        action={"code": "redeem_recognition", "owner": "recognition"},
        handoff=_handoff("recognition", "recognition"),
        links={"detail": "/api/v1/recognition/me/"},
        web={"route": "recognition:dashboard"},
    )

def _discover(*, text, situation):
    query = {"q": text}
    collection = f"{reverse('discovery_api:items')}?{urlencode(query)}"
    return _response(
        state="resolved",
        situation=situation,
        intent="discover_search",
        message="Cette intention ouvre une recherche de possibilités dans Découvrir.",
        result={"kind": "discovery_search", "query": text},
        handoff=_handoff("discovery", "discover"),
        links={"collection": collection},
        web={"route": "discovery:home", "query": query},
    )


def _simple_handoff(
    *,
    situation,
    intent,
    message,
    owner,
    surface,
    api_link,
    web_route,
):
    return _response(
        state="resolved",
        situation=situation,
        intent=intent,
        message=message,
        result={"kind": "handoff"},
        handoff=_handoff(owner, surface),
        links={"detail": api_link},
        web={"route": web_route},
    )


def _unsupported(*, situation, intent, code, message, links=None, handoff=None):
    return _response(
        state="unsupported",
        situation=situation,
        intent=intent,
        message=message,
        result={
            "state": "unsupported",
            "reason": code,
        },
        links=links or {},
        handoff=handoff,
    )


def orchestrate_mark(*, profile, input_kind, value, context=None):
    context = dict(_mapping(context))
    text = str(value or "").strip()[:MARK_TEXT_MAX_LENGTH]
    folded = _fold(text)
    situation = _situation(folded)

    spoofed = sorted(_AUTHORITY_CONTEXT_KEYS.intersection(context))
    if spoofed:
        return _response(
            state="forbidden",
            situation=situation,
            intent="personal_scope",
            message=(
                "Le Makolo Mark personnel agit uniquement pour le Profile connecté. "
                "Le contexte ne peut pas accorder une autorité supplémentaire."
            ),
            result={
                "state": "forbidden",
                "reason": "personal_scope_only",
            },
        )

    if input_kind != "text":
        return _unsupported(
            situation=situation,
            intent="ingest_input",
            code="input_modality_not_exposed",
            message=(
                "Le runtime Mark actuel ne possède pas encore un intake générique "
                f"pour la modalité « {input_kind} »."
            ),
        )

    selected = _selected(context)

    if _contains(
        folded,
        (
            "continue a chercher",
            "continue de chercher",
            "continues a chercher",
            "continues de chercher",
        ),
    ):
        return _ensure_watch(
            profile=profile,
            text=text,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "garde ce document",
            "garde mon document",
            "garde ce cv",
            "garde mon cv",
            "comme ressource",
        ),
    ):
        return _unsupported(
            situation=situation,
            intent="conserve_personal_asset",
            code="file_ingestion_not_exposed",
            message=(
                "Makolo sait gérer les ressources personnelles existantes, "
                "mais le Mark n'expose pas encore un intake de fichier canonique. "
                "Aucun PersonalAsset vide n'a été créé."
            ),
            links={"resources": reverse("personal-projections:resources")},
            handoff=_handoff("personal_assets", "resources"),
        )

    if _contains(
        folded,
        (
            "garde ceci",
            "garde cette possibilite",
            "garde cette activite",
            "enregistre ceci",
            "sauvegarde ceci",
        ),
    ):
        return _save_discovery(
            profile=profile,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "retrouve mon acces",
            "retrouve mes acces",
            "montre mon acces",
            "montre mes acces",
            "mon billet",
            "mon ticket",
            "mes billets",
            "mes tickets",
        ),
    ):
        return _resolve_access(
            profile=profile,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "mon historique",
            "retrouve mon historique",
            "qu'est-ce que j'ai deja fait",
            "qu est ce que j ai deja fait",
            "mon dernier voyage",
            "mes anciennes activites",
        ),
    ):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_history",
            message="Makolo remet la main à votre Historique personnel.",
            owner="history",
            surface="history",
            api_link=reverse("personal-projections:history"),
            web_route="core:participant-history",
        )

    if _contains(folded, ("mon passeport", "montre mon passeport", "passeport makolo")):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_passport",
            message="Makolo ouvre votre Passeport personnel.",
            owner="passport",
            surface="passport",
            api_link=reverse("personal-projections:passport"),
            web_route="sharing:passport-me",
        )

    if _contains(
        folded,
        (
            "ma veille",
            "mes veilles",
            "retrouve ma veille",
            "retrouve mes veilles",
        ),
    ):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_watch",
            message="Makolo ouvre vos Veilles.",
            owner="discovery",
            surface="watches",
            api_link=reverse("discovery_api:watches"),
            web_route="discovery:watch-list",
        )

    if _contains(
        folded,
        (
            "que j'ai garde",
            "que j ai garde",
            "sauvegardee",
            "sauvegarde",
            "mes elements gardes",
            "mes favoris",
        ),
    ) and _contains(folded, ("retrouve", "ouvre", "montre", "mes ")):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_saved",
            message="Makolo ouvre les possibilités que vous avez explicitement gardées.",
            owner="discovery",
            surface="saved",
            api_link=reverse("personal-projections:considerations"),
            web_route="discovery:bookmarks",
        )

    if _contains(
        folded,
        (
            "retrouve mon cv",
            "retrouve mon document",
            "retrouve mon certificat",
            "mes ressources",
            "mes documents",
        ),
    ):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_personal_asset",
            message="Makolo ouvre vos ressources personnelles.",
            owner="personal_assets",
            surface="resources",
            api_link=reverse("personal-projections:resources"),
            web_route="personal_assets:list",
        )

    if _contains(
        folded,
        (
            "je suis arrive",
            "ou dois-je aller maintenant",
            "ou dois je aller maintenant",
            "ce qui se passe en direct",
            "montre ce qui se passe en direct",
        ),
    ):
        return _resolve_live(
            profile=profile,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "que dois-je faire aujourd'hui",
            "que dois je faire aujourd hui",
            "qu'est-ce que je dois faire aujourd'hui",
            "qu est ce que je dois faire aujourd hui",
            "quoi faire maintenant",
            "que dois-je faire maintenant",
            "que dois je faire maintenant",
        ),
    ):
        return _simple_handoff(
            situation=situation,
            intent="inspect_now",
            message="Makolo ouvre ce qui compte maintenant.",
            owner="attention",
            surface="now",
            api_link=reverse("personal-projections:now"),
            web_route="core:participant-home",
        )

    if _contains(folded, ("mon dossier", "mes dossiers", "ce dossier")):
        return _resolve_objective(
            profile=profile,
            situation=situation,
            context=context,
            kind="dossier",
        )

    if _contains(folded, ("mon projet", "mes projets", "ce projet")):
        return _resolve_objective(
            profile=profile,
            situation=situation,
            context=context,
            kind="project",
        )

    if _contains(folded, ("mes recompenses", "ma reconnaissance", "mes reconnaissances")):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_recognition",
            message="Makolo ouvre votre relation de Reconnaissance.",
            owner="recognition",
            surface="recognition",
            api_link="/api/v1/recognition/me/",
            web_route="recognition:dashboard",
        )

    if _contains(folded, ("mes avantages", "ma fidelite", "mon programme de fidelite")):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_loyalty",
            message="Makolo ouvre vos relations de fidélité.",
            owner="loyalty",
            surface="loyalty",
            api_link="/api/v1/loyalty/me/",
            web_route="loyalty:dashboard",
        )

    if _contains(folded, ("mes partenaires", "ma relation partenaire", "mes relations partenaires")):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_partner",
            message="Makolo ouvre vos relations partenaires personnelles.",
            owner="partner",
            surface="partners",
            api_link=reverse("personal-projections:partners"),
            web_route="core:participant-me",
        )

    journey_language = _contains(
        folded,
        (
            "candidature",
            "demarche",
            "ou en est",
            "reprendre ma",
            "reprendre mon",
            "continuer ma",
            "continuer mon",
            "qu'est-ce qu'il manque",
            "qu est ce qu il manque",
        ),
    )
    if selected["kind"] == "journey" and _contains(
        folded,
        ("continue", "ouvre", "manque", "pourquoi", "reprends", "reprendre"),
    ):
        journey_language = True
    if journey_language:
        return _resolve_journey(
            profile=profile,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "paie maintenant",
            "paye maintenant",
            "effectue le paiement",
        ),
    ):
        journey = _resolve_journey(
            profile=profile,
            situation=situation,
            context=context,
            intent="pay",
        )
        if journey["state"] in {"resolved", "needs_clarification", "unknown"}:
            journey["_web"] = None
            if journey["state"] == "resolved" and journey["result"].get("kind") == "journey":
                journey["state"] = "unsupported"
                journey["message"] = (
                    "Le Mark ne possède pas de capability Payment propriétaire "
                    "confirmée pour cette démarche. Il n'a initié aucun paiement."
                )
                journey["result"] = {
                    "state": "unsupported",
                    "reason": "payment_capability_not_exposed",
                }
            return journey

    if _contains(
        folded,
        (
            "utilise cette recompense",
            "utilise ma recompense",
        ),
    ):
        return _redeem_recognition(
            profile=profile,
            situation=situation,
            context=context,
        )

    if _contains(
        folded,
        (
            "m'interesse durablement",
            "m interesse durablement",
            "ajoute a mes interets",
        ),
    ):
        return _unsupported(
            situation=situation,
            intent="set_interest",
            code="interest_mutation_not_exposed",
            message=(
                "Le Mark ne transforme pas une phrase en Interest sans contrat "
                "de mutation explicite. Aucun Interest n'a été créé."
            ),
            links={"considerations": reverse("personal-projections:considerations")},
            handoff=_handoff("profile", "considerations"),
        )

    if _contains(
        folded,
        (
            "organise ",
            "cree une activite",
            "cree un evenement",
            "publie ceci",
        ),
    ):
        return _unsupported(
            situation=situation,
            intent="create_reality",
            code="creation_or_publication_not_exposed",
            message=(
                "Le Mark comprend l'intention de faire exister quelque chose, "
                "mais aucun owner-domain creation contract stable n'est exposé "
                "ici. Rien n'a été créé ni publié."
            ),
        )

    if _contains(
        folded,
        (
            "negocie automatiquement",
            "negocie le prix",
        ),
    ):
        return _unsupported(
            situation=situation,
            intent="unsupported_action",
            code="capability_not_available",
            message="Makolo ne possède pas actuellement cette capacité.",
        )

    if _contains(
        folded,
        (
            "je cherche",
            "trouve-moi",
            "trouve moi",
            "je veux trouver",
            "je veux voyager",
            "cherche une",
            "cherche un",
            "trouve une",
            "trouve un",
            "quoi faire ce soir",
            "ou aller",
        ),
    ):
        return _discover(text=text, situation=situation)

    if _contains(
        folded,
        (
            "retrouve mon",
            "retrouve ma",
            "retrouver mon",
            "retrouver ma",
            "ou est mon",
            "ou est ma",
        ),
    ):
        return _simple_handoff(
            situation=situation,
            intent="retrieve_known",
            message=(
                "Makolo remet la main à Moi, qui compose les réalités "
                "personnelles déjà connues sans lancer une recherche ouverte."
            ),
            owner="profile",
            surface="me",
            api_link=reverse("personal-projections:me"),
            web_route="core:participant-me",
        )

    if situation in {"have", "changed", "understand"}:
        return _clarification(
            situation=situation,
            intent="clarify_intent",
            code="what_consequence",
            summary=(
                "Makolo a besoin d'une seule précision pour savoir quelle "
                "conséquence utile produire à partir de cela."
            ),
        )

    return _clarification(
        situation=situation,
        intent="unknown",
        code="what_do_you_mean",
        summary=(
            "Makolo ne peut pas encore relier cette demande à une capacité "
            "réellement disponible. Précisez ce que vous voulez obtenir."
        ),
    )

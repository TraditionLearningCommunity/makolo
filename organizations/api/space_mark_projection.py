from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from uuid import UUID

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError

from activities.models import Occurrence
from activities.selectors import occurrence_with_places
from authorization.constants import PermissionCode
from authorization.services import can
from operations.space_day_of import build_space_operator_day_of
from organizations.services import add_or_update_member, find_user_for_team
from scanner.space_context import build_scanner_context


def _fold(value):
    value = " ".join(str(value or "").casefold().split())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _response(*, state, intent, message, result=None, question=None, action=None, handoff=None, links=None):
    return {
        "state": state,
        "understanding": {"intent": intent},
        "result": result,
        "question": question,
        "action": action,
        "handoff": handoff,
        "links": links or {},
        "message": message,
    }


def _occurrence_reference(context):
    selected = _mapping(context.get("selected"))
    raw = selected.get("id") if selected.get("kind") == "occurrence" else context.get("occurrence_id")
    return str(raw or "").strip()


def _occurrence_from_context(*, space, context):
    raw = _occurrence_reference(context)
    occurrence_id = _uuid(raw)
    if occurrence_id is None:
        return None
    try:
        occurrence = occurrence_with_places(occurrence_id)
    except Occurrence.DoesNotExist:
        return None
    if occurrence.activity.space_id != space.pk:
        return None
    return occurrence


def orchestrate_space_mark(*, profile, space, input_kind, value, context, observed_at=None):
    responsibility = str(_mapping(context).get("responsibility") or "").strip() or None
    if input_kind != "text":
        return _response(
            state="unsupported",
            intent="unsupported_input",
            message="Ce contexte Space accepte actuellement uniquement du texte.",
            result={"reason": "input_kind_not_supported"},
        )

    folded = _fold(value)

    if any(term in folded for term in ("jour j", "live", "maintenant sur place", "ce qui se passe")):
        raw_occurrence = _occurrence_reference(context)
        occurrence = _occurrence_from_context(space=space, context=context)
        if occurrence is None:
            if raw_occurrence:
                return _response(
                    state="unknown",
                    intent="inspect_day_of",
                    message="Cette cible n’est pas disponible dans ce contexte.",
                    result={"reason": "target_not_available"},
                )
            return _response(
                state="needs_clarification",
                intent="inspect_day_of",
                message="Makolo a besoin de l’Occurrence concernée.",
                question={"code": "which_occurrence", "options": []},
            )
        day_of = build_space_operator_day_of(
            occurrence=occurrence,
            actor=profile,
            observed_at=observed_at,
        )
        if day_of is None:
            return _response(
                state="unknown",
                intent="inspect_day_of",
                message="Aucune surface Jour J opérateur accessible n’est disponible pour ce contexte.",
                result={"reason": "day_of_not_available"},
            )
        return _response(
            state="resolved",
            intent="inspect_day_of",
            message="Makolo a retrouvé le Jour J de cette Occurrence.",
            result={
                "identity": day_of["identity"],
                "responsibility": responsibility,
            },
            handoff={"owner": "operations", "surface": "day_of"},
            links={
                "day_of": f"/api/v1/operations/occurrences/{occurrence.pk}/day-of/",
                "live": f"/api/v1/operations/occurrences/{occurrence.pk}/live/",
            },
        )

    if any(term in folded for term in ("scanner", "scan", "controle", "controler", "verifier un acces")):
        raw_occurrence = _occurrence_reference(context)
        occurrence = _occurrence_from_context(space=space, context=context)
        if occurrence is None:
            if raw_occurrence:
                return _response(
                    state="unknown",
                    intent="open_scanner",
                    message="Cette cible n’est pas disponible dans ce contexte.",
                    result={"reason": "target_not_available"},
                )
            return _response(
                state="needs_clarification",
                intent="open_scanner",
                message="Makolo a besoin de l’Occurrence à contrôler.",
                question={"code": "which_occurrence", "options": []},
            )
        scanner = build_scanner_context(
            occurrence=occurrence,
            actor=profile,
            observed_at=observed_at,
        )
        if scanner is None:
            if not can(profile, PermissionCode.ACTIVITY_VIEW, activity=occurrence.activity):
                return _response(
                    state="unknown",
                    intent="open_scanner",
                    message="Cette cible n’est pas disponible dans ce contexte.",
                    result={"reason": "target_not_available"},
                )
            return _response(
                state="forbidden",
                intent="open_scanner",
                message="Le contrôle n’est pas autorisé dans ce scope.",
                result={"reason": "scanner_authority_required"},
            )
        return _response(
            state="resolved",
            intent="open_scanner",
            message="Makolo a préparé le contexte de contrôle.",
            result={
                "identity": scanner["identity"],
                "responsibility": responsibility,
            },
            handoff={"owner": "scanner", "surface": "occurrence_context"},
            links={
                "context": f"/api/v1/scanner/occurrences/{occurrence.pk}/context/",
                **({"scan": scanner["links"]["scan"]} if "scan" in scanner["links"] else {}),
            },
        )

    if any(term in folded for term in ("equipe", "team", "ajoute paul", "ajoute marie", "ajoute un membre")):
        team_link = f"/api/v1/organizations/workspaces/{space.slug}/team/"
        if not can(profile, PermissionCode.SPACE_TEAM_MANAGE, space):
            return _response(
                state="forbidden",
                intent="add_team_member" if "ajoute" in folded else "open_team",
                message="Cette surface exige une autorité Team réelle.",
                result={"reason": "team_manage_authority_required"},
            )

        if "ajoute" in folded:
            team_member = _mapping(context.get("team_member"))
            email = str(team_member.get("email") or "").strip().lower()
            role = str(team_member.get("role") or "").strip()
            if not email or not role:
                return _response(
                    state="needs_clarification",
                    intent="add_team_member",
                    message="Il faut identifier précisément le Profil et le rôle d’autorité à lui attribuer.",
                    question={"code": "team_member_identity_and_responsibility", "options": []},
                    handoff={"owner": "organizations", "surface": "team"},
                    links={"owner": team_link},
                )

            action = {
                "code": "add_team_member",
                "consequence": f"Ajouter {email} à l’équipe de {space.name} avec le rôle d’autorité {role}.",
                "target": {"email": email, "role": role},
            }
            confirmation = _mapping(context.get("confirmation"))
            confirmed = (
                confirmation.get("code") == action["code"]
                and str(confirmation.get("email") or "").strip().lower() == email
                and str(confirmation.get("role") or "").strip() == role
            )
            if not confirmed:
                return _response(
                    state="needs_confirmation",
                    intent="add_team_member",
                    message="Cette action modifiera réellement l’équipe du Space.",
                    action=action,
                    handoff={"owner": "organizations", "surface": "team"},
                    links={"owner": team_link},
                )

            # Revalidate authority immediately before the owner mutation.
            if not can(profile, PermissionCode.SPACE_TEAM_MANAGE, space):
                return _response(
                    state="forbidden",
                    intent="add_team_member",
                    message="L’autorité nécessaire n’est plus disponible.",
                    result={"reason": "team_manage_authority_required"},
                )
            try:
                target = find_user_for_team(email=email)
                membership = add_or_update_member(
                    organization=space,
                    actor=profile,
                    user=target,
                    role=role,
                )
            except DjangoPermissionDenied:
                return _response(
                    state="forbidden",
                    intent="add_team_member",
                    message="L’autorité nécessaire n’est plus disponible.",
                    result={"reason": "team_manage_authority_required"},
                )
            except DjangoValidationError:
                return _response(
                    state="needs_clarification",
                    intent="add_team_member",
                    message="Le domaine Organizations ne peut pas appliquer cette demande telle quelle.",
                    question={"code": "team_member_details_invalid", "options": []},
                    handoff={"owner": "organizations", "surface": "team"},
                    links={"owner": team_link},
                )
            return _response(
                state="completed",
                intent="add_team_member",
                message="Le domaine Organizations a mis à jour l’équipe.",
                result={
                    "kind": "team_membership",
                    "id": str(membership.pk),
                    "profile_id": str(membership.user_id),
                    "responsibility": role,
                },
                handoff={"owner": "organizations", "surface": "team"},
                links={"owner": team_link},
            )

        return _response(
            state="resolved",
            intent="open_team",
            message="Makolo a retrouvé la surface Équipe de ce Space.",
            result={"responsibility": responsibility},
            handoff={"owner": "organizations", "surface": "team"},
            links={"owner": team_link},
        )

    if any(term in folded for term in ("depart", "commande", "partenaire", "finance", "paiement")):
        return _response(
            state="unsupported",
            intent="owner_handoff",
            message="Le handoff owner demandé n’est pas encore stable sur cette base ZS5.",
            result={"reason": "owner_handoff_not_available_on_base"},
        )

    return _response(
        state="unknown",
        intent="unknown",
        message="Makolo n’a pas assez d’éléments pour déterminer un handoff Space sûr.",
        result={"reason": "intent_not_resolved"},
    )

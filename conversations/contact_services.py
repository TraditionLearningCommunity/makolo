from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from social.models import ActionNetworkBlock, ActionProposalStatus

from .audience_services import profile_in_audience
from .contact_models import (
    CommunicationRoute,
    CommunicationRouteStatus,
    ContactPolicyMode,
    ContactRequest,
    ContactRequestStatus,
    ProfileContactPolicy,
)
from .core_models import ConversationContextKind, ConversationEntryMode, ConversationHistoryPolicy
from .services import can_manage_conversation_routes, ensure_context_conversation


def profiles_blocked(profile_a, profile_b) -> bool:
    return ActionNetworkBlock.objects.filter(
        Q(blocker_profile=profile_a, blocked_profile=profile_b)
        | Q(blocker_profile=profile_b, blocked_profile=profile_a)
    ).exists()


def contact_policy_for(profile):
    policy, _ = ProfileContactPolicy.objects.get_or_create(profile=profile)
    if policy.valid_until and timezone.now() >= policy.valid_until:
        policy.mode = ContactPolicyMode.REQUEST
    return policy


def _accepted_contact_request(sender, recipient):
    return ContactRequest.objects.filter(
        Q(sender=sender, recipient=recipient) | Q(sender=recipient, recipient=sender),
        status=ContactRequestStatus.ACCEPTED,
    ).exists()


def _accepted_proposal_between(profile_a, profile_b):
    from social.models import ActionProposal
    return ActionProposal.objects.filter(
        status=ActionProposalStatus.ACCEPTED,
    ).filter(
        Q(need__owner_profile=profile_a, candidate_profile=profile_b)
        | Q(need__owner_profile=profile_b, candidate_profile=profile_a)
    ).exists()


def can_start_direct_conversation(actor, target) -> bool:
    if not getattr(actor, "is_authenticated", False) or not target or actor.pk == target.pk:
        return False
    if profiles_blocked(actor, target):
        return False
    if _accepted_contact_request(actor, target) or _accepted_proposal_between(actor, target):
        return True
    policy = contact_policy_for(target)
    return policy.mode == ContactPolicyMode.DIRECT


@transaction.atomic
def create_contact_request(*, actor, recipient, intent, message, expires_at=None, client_reference=None):
    if not getattr(actor, "is_authenticated", False) or actor.pk == recipient.pk:
        raise ValidationError("Cette demande de contact n’est pas valide.")
    if profiles_blocked(actor, recipient):
        raise ValidationError("Cette mise en relation n’est pas disponible.")
    policy = contact_policy_for(recipient)
    if policy.mode == ContactPolicyMode.CLOSED:
        raise ValidationError("Cette mise en relation n’est pas disponible.")
    if intent == "other" and not policy.allow_other_requests:
        raise ValidationError("Cette intention de contact n’est pas disponible.")
    ref = (client_reference or "").strip() or None
    if ref:
        existing = ContactRequest.objects.filter(client_reference=ref).first()
        if existing:
            if existing.sender_id == actor.pk and existing.recipient_id == recipient.pk:
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    request = ContactRequest(sender=actor, recipient=recipient, intent=intent, message=message, expires_at=expires_at, client_reference=ref)
    try:
        request.save()
    except IntegrityError as exc:
        raise ValidationError("Une demande de contact similaire est déjà en attente.") from exc
    return request


@transaction.atomic
def respond_to_contact_request(*, actor, contact_request, accept: bool):
    locked = ContactRequest.objects.select_for_update().get(pk=contact_request.pk)
    if locked.recipient_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seul le destinataire peut répondre à cette demande.")
    if locked.status != ContactRequestStatus.PENDING:
        return locked
    now = timezone.now()
    if locked.expires_at and now >= locked.expires_at:
        locked.status = ContactRequestStatus.EXPIRED
    else:
        locked.status = ContactRequestStatus.ACCEPTED if accept else ContactRequestStatus.DECLINED
    locked.responded_at = now
    locked.save(update_fields=["status", "responded_at", "updated_at"])
    return locked


@transaction.atomic
def ensure_direct_conversation(*, actor, target, purpose_key="coordination", title_override=""):
    if not can_start_direct_conversation(actor, target):
        raise PermissionDenied("Cette Conversation directe n’est pas disponible sans contexte ou consentement.")
    return ensure_context_conversation(
        actor=actor,
        kind=ConversationContextKind.DIRECT,
        direct_profile_a=actor,
        direct_profile_b=target,
        purpose_key=purpose_key,
        separation_reason="Contact direct explicitement consenti" if purpose_key != "coordination" else "",
        title_override=title_override,
        entry_mode=ConversationEntryMode.DIRECT_CONSENT,
        history_policy=ConversationHistoryPolicy.FROM_JOIN,
    )


@transaction.atomic
def ensure_proposal_conversation(*, actor, proposal):
    if proposal.status != ActionProposalStatus.ACCEPTED:
        raise ValidationError("Une Conversation de proposition exige une proposition acceptée.")
    allowed = proposal.candidate_profile_id == getattr(actor, "pk", None) or proposal.need.owner_profile_id == getattr(actor, "pk", None)
    if not allowed:
        # Space representation remains checked by the canonical Conversation authority resolver.
        from .services import _has_scope_permission
        from .core_models import ConversationContext
        probe = ConversationContext(kind=ConversationContextKind.ACTION_PROPOSAL, action_proposal=proposal)
        allowed = _has_scope_permission(actor, probe, "MANAGE")
    if not allowed:
        raise PermissionDenied("Vous ne faites pas partie de cette proposition.")
    return ensure_context_conversation(
        actor=actor,
        kind=ConversationContextKind.ACTION_PROPOSAL,
        action_proposal=proposal,
        purpose_key="coordination",
        entry_mode=ConversationEntryMode.DERIVED,
        history_policy=ConversationHistoryPolicy.FROM_JOIN,
    )


@transaction.atomic
def create_communication_route(*, actor, conversation, provider, destination_kind, label, destination, purpose="", audience=None, expires_at=None):
    if not can_manage_conversation_routes(actor, conversation):
        raise PermissionDenied("Vous ne pouvez pas gérer les routes externes de cette Conversation.")
    route = CommunicationRoute(
        conversation=conversation,
        provider=provider,
        destination_kind=destination_kind,
        label=label,
        purpose=purpose,
        destination=destination,
        audience=audience,
        expires_at=expires_at,
        created_by=actor,
    )
    route.save()
    return route


def communication_routes_for(profile, conversation, *, at=None):
    at = at or timezone.now()
    result = []
    for route in conversation.communication_routes.filter(status=CommunicationRouteStatus.ACTIVE).select_related("audience"):
        if route.expires_at and route.expires_at <= at:
            continue
        if route.audience_id and not profile_in_audience(profile, route.audience, at=at):
            continue
        result.append(route)
    return result

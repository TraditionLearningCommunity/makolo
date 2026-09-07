from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import GroupMembership, GroupMembershipStatus

from .models import (
    Conversation,
    ConversationContext,
    ConversationContextKind,
    ConversationDiscoverability,
    ConversationEntryMode,
    ConversationHistoryPolicy,
    ConversationInvitation,
    ConversationInvitationStatus,
    ConversationJoinRequest,
    ConversationJoinRequestStatus,
    ConversationLifecycle,
    ConversationModePreset,
    ConversationParticipation,
    ConversationParticipationSource,
    ConversationParticipationStatus,
    ConversationPolicy,
    ConversationUserState,
)


LIFECYCLE_TRANSITIONS = {
    ConversationLifecycle.DRAFT: {ConversationLifecycle.OPEN, ConversationLifecycle.ARCHIVED},
    ConversationLifecycle.OPEN: {ConversationLifecycle.CLOSED, ConversationLifecycle.ARCHIVED},
    ConversationLifecycle.CLOSED: {ConversationLifecycle.OPEN, ConversationLifecycle.ARCHIVED},
    ConversationLifecycle.ARCHIVED: set(),
}


POLICY_PRESETS = {
    ConversationModePreset.ANNOUNCEMENTS: {
        "allow_information": True,
        "allow_questions": True,
        "allow_confirmations": True,
        "allow_polls": True,
        "allow_requests": True,
        "allow_form_requests": True,
        "allow_free_exchange": False,
        "allow_voice": False,
        "allow_images": True,
        "allow_video": False,
        "allow_documents": True,
        "allow_links": True,
    },
    ConversationModePreset.GUIDED: {
        "allow_information": True,
        "allow_questions": True,
        "allow_confirmations": True,
        "allow_polls": True,
        "allow_requests": True,
        "allow_form_requests": True,
        "allow_free_exchange": False,
        "allow_voice": True,
        "allow_images": True,
        "allow_video": False,
        "allow_documents": True,
        "allow_links": True,
    },
    ConversationModePreset.MIXED: {
        "allow_information": True,
        "allow_questions": True,
        "allow_confirmations": True,
        "allow_polls": True,
        "allow_requests": True,
        "allow_form_requests": True,
        "allow_free_exchange": True,
        "allow_voice": True,
        "allow_images": True,
        "allow_video": False,
        "allow_documents": True,
        "allow_links": True,
    },
    ConversationModePreset.FREE: {
        "allow_information": True,
        "allow_questions": True,
        "allow_confirmations": True,
        "allow_polls": True,
        "allow_requests": True,
        "allow_form_requests": True,
        "allow_free_exchange": True,
        "allow_voice": True,
        "allow_images": True,
        "allow_video": True,
        "allow_documents": True,
        "allow_links": True,
    },
}


def _authenticated(actor) -> bool:
    return bool(actor and getattr(actor, "is_authenticated", False))


def _activity_for_context(context):
    if context.kind == ConversationContextKind.ACTIVITY:
        return context.activity
    if context.kind == ConversationContextKind.OCCURRENCE:
        return context.occurrence.activity
    if context.kind == ConversationContextKind.JOURNEY:
        return context.journey.activity
    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        return context.action_proposal.need.activity
    return None


def _space_for_context(context):
    if context.kind == ConversationContextKind.SPACE:
        return context.space
    if context.kind == ConversationContextKind.GROUP and context.group.space_id:
        return context.group.space
    activity = _activity_for_context(context)
    if activity is not None and activity.space_id:
        return activity.space
    if context.kind == ConversationContextKind.DOSSIER:
        return context.dossier.owning_space
    if context.kind == ConversationContextKind.PROJECT:
        return context.project.owning_space
    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        return context.action_proposal.need.space
    return None


def _personal_owner_for_context(context):
    if context.kind == ConversationContextKind.GROUP:
        return context.group.owner_profile
    if context.kind == ConversationContextKind.ACTIVITY:
        return context.activity.owner_profile
    if context.kind == ConversationContextKind.OCCURRENCE:
        return context.occurrence.activity.owner_profile
    if context.kind == ConversationContextKind.DOSSIER:
        return context.dossier.owner_profile
    if context.kind == ConversationContextKind.PROJECT:
        return context.project.owner_profile
    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        return context.action_proposal.need.owner_profile
    return None


def _has_scope_permission(actor, context, permission_suffix: str) -> bool:
    if not _authenticated(actor):
        return False
    if getattr(actor, "is_superuser", False) or can(actor, PermissionCode.PLATFORM_MANAGE):
        return True

    personal_owner = _personal_owner_for_context(context)
    if personal_owner is not None and personal_owner.pk == actor.pk:
        return True

    if context.kind == ConversationContextKind.SPACE:
        return can(actor, getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}"), space=context.space)

    if context.kind == ConversationContextKind.GROUP:
        permission = getattr(PermissionCode, f"GROUP_CONVERSATIONS_{permission_suffix}")
        if can(actor, permission, group=context.group):
            return True
        if context.group.space_id:
            space_permission = getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}")
            return can(actor, space_permission, space=context.group.space)
        return False

    if context.kind in {ConversationContextKind.ACTIVITY, ConversationContextKind.OCCURRENCE}:
        activity = _activity_for_context(context)
        permission = getattr(PermissionCode, f"ACTIVITY_CONVERSATIONS_{permission_suffix}")
        return can(actor, permission, activity=activity)

    if context.kind == ConversationContextKind.DOSSIER:
        permission = getattr(PermissionCode, f"DOSSIER_CONVERSATIONS_{permission_suffix}")
        if can(actor, permission, dossier=context.dossier):
            return True
        if context.dossier.owning_space_id:
            space_permission = getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}")
            return can(actor, space_permission, space=context.dossier.owning_space)
        return False

    if context.kind == ConversationContextKind.PROJECT:
        if context.project.owner_profile_id == actor.pk:
            return True
        if context.project.owning_space_id:
            space_permission = getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}")
            return can(actor, space_permission, space=context.project.owning_space)
        return False

    if context.kind == ConversationContextKind.JOURNEY:
        if actor.pk in {context.journey.beneficiary_id, context.journey.initiated_by_id}:
            return True
        activity = context.journey.activity
        permission = getattr(PermissionCode, f"ACTIVITY_CONVERSATIONS_{permission_suffix}")
        return can(actor, permission, activity=activity)

    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        proposal = context.action_proposal
        need = proposal.need
        if need.owner_profile_id == actor.pk or proposal.candidate_profile_id == actor.pk:
            return True
        if proposal.candidate_space_id:
            space_permission = getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}")
            if can(actor, space_permission, space=proposal.candidate_space):
                return True
        if need.activity_id:
            activity_permission = getattr(PermissionCode, f"ACTIVITY_CONVERSATIONS_{permission_suffix}")
            if can(actor, activity_permission, activity=need.activity):
                return True
        if need.space_id:
            space_permission = getattr(PermissionCode, f"SPACE_CONVERSATIONS_{permission_suffix}")
            return can(actor, space_permission, space=need.space)
        return False

    if context.kind == ConversationContextKind.DIRECT:
        return actor.pk in {context.direct_profile_a_id, context.direct_profile_b_id}

    return False


def can_manage_conversation(actor, conversation: Conversation) -> bool:
    try:
        context = conversation.context
    except ConversationContext.DoesNotExist:
        return False
    return _has_scope_permission(actor, context, "MANAGE")


def can_publish_in_conversation(actor, conversation: Conversation) -> bool:
    try:
        context = conversation.context
    except ConversationContext.DoesNotExist:
        return False
    return _has_scope_permission(actor, context, "PUBLISH")


def can_moderate_conversation(actor, conversation: Conversation) -> bool:
    try:
        context = conversation.context
    except ConversationContext.DoesNotExist:
        return False
    return _has_scope_permission(actor, context, "MODERATE")


def can_manage_conversation_routes(actor, conversation: Conversation) -> bool:
    try:
        context = conversation.context
    except ConversationContext.DoesNotExist:
        return False
    return _has_scope_permission(actor, context, "ROUTES_MANAGE")


def _action_proposal_party(actor, proposal) -> bool:
    if proposal.need.owner_profile_id == actor.pk or proposal.candidate_profile_id == actor.pk:
        return True
    if proposal.need.space_id and can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=proposal.need.space):
        return True
    if proposal.candidate_space_id and can(actor, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=proposal.candidate_space):
        return True
    return False


def context_base_eligible(actor, context: ConversationContext) -> bool:
    """Conservative J1 eligibility. J2 extends collective audiences without weakening this boundary."""

    if not _authenticated(actor):
        return False
    if _has_scope_permission(actor, context, "MANAGE") or _has_scope_permission(actor, context, "PUBLISH"):
        return True
    if context.kind == ConversationContextKind.GROUP:
        return GroupMembership.objects.filter(
            group=context.group,
            profile=actor,
            status=GroupMembershipStatus.ACTIVE,
        ).exists()
    if context.kind == ConversationContextKind.JOURNEY:
        return actor.pk in {context.journey.beneficiary_id, context.journey.initiated_by_id}
    if context.kind == ConversationContextKind.ACTION_PROPOSAL:
        return _action_proposal_party(actor, context.action_proposal)
    if context.kind == ConversationContextKind.DIRECT:
        return actor.pk in {context.direct_profile_a_id, context.direct_profile_b_id}
    if context.kind in {ConversationContextKind.ACTIVITY, ConversationContextKind.OCCURRENCE}:
        activity = _activity_for_context(context)
        if activity.owner_profile_id == actor.pk:
            return True
    if context.kind == ConversationContextKind.DOSSIER:
        return context.dossier.owner_profile_id == actor.pk
    if context.kind == ConversationContextKind.PROJECT:
        return context.project.owner_profile_id == actor.pk
    return False


def can_view_conversation(actor, conversation: Conversation) -> bool:
    if not _authenticated(actor):
        return False
    try:
        from .audience_services import conversation_viewer_ids

        return actor.pk in conversation_viewer_ids(conversation)
    except ConversationContext.DoesNotExist:
        return False


def _context_lookup(kind, *, purpose_key, targets):
    lookup = {"kind": kind, "purpose_key": purpose_key}
    if kind == ConversationContextKind.DIRECT:
        a = targets.get("direct_profile_a")
        b = targets.get("direct_profile_b")
        if a is None or b is None:
            return lookup
        if str(a.pk) > str(b.pk):
            a, b = b, a
        lookup.update(direct_profile_a=a, direct_profile_b=b)
    else:
        field = ConversationContext.TARGET_FIELDS[kind][0]
        lookup[field] = targets.get(field)
    return lookup


def _new_unsaved_context(*, kind, purpose_key, separation_reason, targets):
    return ConversationContext(
        kind=kind,
        purpose_key=purpose_key,
        separation_reason=separation_reason,
        **{field: targets.get(field) for fields in ConversationContext.TARGET_FIELDS.values() for field in fields},
    )


def _create_policy(*, conversation, preset):
    values = POLICY_PRESETS[preset]
    return ConversationPolicy.objects.create(conversation=conversation, preset=preset, **values)


@transaction.atomic
def ensure_context_conversation(
    *,
    actor,
    kind,
    purpose_key="coordination",
    separation_reason="",
    title_override="",
    purpose="",
    mode_preset=ConversationModePreset.MIXED,
    entry_mode=ConversationEntryMode.DERIVED,
    discoverability=ConversationDiscoverability.HIDDEN,
    history_policy=ConversationHistoryPolicy.CONTEXT_HISTORY,
    client_reference=None,
    open_immediately=True,
    **targets,
) -> Conversation:
    if not _authenticated(actor):
        raise PermissionDenied("Authentification requise pour créer une Conversation.")
    purpose_key = (purpose_key or "coordination").strip().lower()
    lookup = _context_lookup(kind, purpose_key=purpose_key, targets=targets)
    existing_context = ConversationContext.objects.select_related("conversation").filter(**lookup).first()
    if existing_context:
        return existing_context.conversation

    context = _new_unsaved_context(
        kind=kind,
        purpose_key=purpose_key,
        separation_reason=separation_reason,
        targets=targets,
    )
    context.clean()
    if not _has_scope_permission(actor, context, "MANAGE"):
        raise PermissionDenied("Vous n’avez pas l’autorité nécessaire pour créer cette Conversation.")

    conversation = Conversation(
        title_override=title_override,
        purpose=purpose,
        lifecycle=ConversationLifecycle.DRAFT,
        mode_preset=mode_preset,
        entry_mode=entry_mode,
        discoverability=discoverability,
        history_policy=history_policy,
        client_reference=(client_reference or "").strip() or None,
        created_by=actor,
    )
    conversation.save()
    context.conversation = conversation
    try:
        context.save()
    except IntegrityError:
        canonical = ConversationContext.objects.select_related("conversation").get(**lookup)
        conversation.delete()
        return canonical.conversation
    _create_policy(conversation=conversation, preset=mode_preset)
    if open_immediately:
        return transition_conversation(actor=actor, conversation=conversation, lifecycle=ConversationLifecycle.OPEN)
    return conversation


@transaction.atomic
def transition_conversation(*, actor, conversation: Conversation, lifecycle: str) -> Conversation:
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if not can_manage_conversation(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas changer l’état de cette Conversation.")
    if locked.lifecycle == lifecycle:
        return locked
    if lifecycle not in LIFECYCLE_TRANSITIONS.get(locked.lifecycle, set()):
        raise ValidationError({"lifecycle": "Transition de Conversation invalide."})
    now = timezone.now()
    locked.lifecycle = lifecycle
    if lifecycle == ConversationLifecycle.OPEN:
        locked.opened_at = locked.opened_at or now
        locked.closed_at = None
    elif lifecycle == ConversationLifecycle.CLOSED:
        locked.closed_at = now
    elif lifecycle == ConversationLifecycle.ARCHIVED:
        locked.archived_at = now
    locked._allow_lifecycle_transition = True
    locked.save(update_fields=["lifecycle", "opened_at", "closed_at", "archived_at", "updated_at"])
    return locked


@transaction.atomic
def set_conversation_policy(*, actor, conversation: Conversation, preset: str) -> ConversationPolicy:
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if not can_manage_conversation(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas modifier la politique de cette Conversation.")
    if preset not in POLICY_PRESETS:
        raise ValidationError({"preset": "Preset Conversation inconnu."})
    policy, _ = ConversationPolicy.objects.select_for_update().get_or_create(conversation=locked)
    policy.preset = preset
    for field, value in POLICY_PRESETS[preset].items():
        setattr(policy, field, value)
    policy.save()
    locked.mode_preset = preset
    locked.save(update_fields=["mode_preset", "updated_at"])
    return policy


@transaction.atomic
def activate_participation(
    *, actor, conversation: Conversation, profile, source=ConversationParticipationSource.MANUAL, represented_space=None
) -> ConversationParticipation:
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if actor.pk != profile.pk and not can_manage_conversation(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas ajouter cette personne à la Conversation.")
    participation, _ = ConversationParticipation.objects.select_for_update().get_or_create(
        conversation=locked,
        profile=profile,
        defaults={
            "source": source,
            "represented_space": represented_space,
            "created_by": actor,
        },
    )
    participation.status = ConversationParticipationStatus.ACTIVE
    participation.source = source
    participation.represented_space = represented_space
    participation.joined_at = timezone.now()
    participation.left_at = None
    participation.removed_at = None
    participation.save()
    return participation


@transaction.atomic
def leave_conversation(*, actor, conversation: Conversation) -> ConversationParticipation:
    participation = ConversationParticipation.objects.select_for_update().filter(
        conversation=conversation,
        profile=actor,
        status=ConversationParticipationStatus.ACTIVE,
    ).first()
    if not participation:
        raise ValidationError("Cette Conversation provient d’un accès contextuel ou n’a pas de participation explicite à quitter.")
    participation.status = ConversationParticipationStatus.LEFT
    participation.left_at = timezone.now()
    participation.save(update_fields=["status", "left_at", "updated_at"])
    return participation


@transaction.atomic
def remove_participation(*, actor, participation: ConversationParticipation) -> ConversationParticipation:
    locked = ConversationParticipation.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=participation.pk)
    if not can_manage_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas retirer cette participation.")
    if locked.status == ConversationParticipationStatus.REMOVED:
        return locked
    locked.status = ConversationParticipationStatus.REMOVED
    locked.removed_at = timezone.now()
    locked.save(update_fields=["status", "removed_at", "updated_at"])
    return locked


@transaction.atomic
def create_conversation_invitation(*, actor, conversation: Conversation, invitee, represented_space=None, expires_at=None, client_reference=None):
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if not can_manage_conversation(actor, locked):
        raise PermissionDenied("Vous ne pouvez pas inviter dans cette Conversation.")
    normalized_reference = (client_reference or "").strip() or None
    if normalized_reference:
        existing = ConversationInvitation.objects.filter(client_reference=normalized_reference).first()
        if existing:
            if existing.conversation_id == locked.pk and existing.invitee_id == invitee.pk:
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    invitation = ConversationInvitation(
        conversation=locked,
        invitee=invitee,
        represented_space=represented_space,
        expires_at=expires_at,
        client_reference=normalized_reference,
        created_by=actor,
    )
    try:
        invitation.save()
    except IntegrityError as exc:
        raise ValidationError("Une invitation en attente existe déjà pour cette personne.") from exc
    return invitation


@transaction.atomic
def respond_to_conversation_invitation(*, actor, invitation: ConversationInvitation, accept: bool):
    locked = ConversationInvitation.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=invitation.pk)
    if locked.invitee_id != getattr(actor, "pk", None):
        raise PermissionDenied("Seule la personne invitée peut répondre.")
    if locked.status != ConversationInvitationStatus.PENDING:
        return locked
    now = timezone.now()
    if locked.expires_at and now >= locked.expires_at:
        locked.status = ConversationInvitationStatus.EXPIRED
        locked.responded_at = now
        locked.save(update_fields=["status", "responded_at", "updated_at"])
        return locked
    locked.status = ConversationInvitationStatus.ACCEPTED if accept else ConversationInvitationStatus.DECLINED
    locked.responded_at = now
    locked.save(update_fields=["status", "responded_at", "updated_at"])
    if accept:
        activate_participation(
            actor=actor,
            conversation=locked.conversation,
            profile=actor,
            source=ConversationParticipationSource.INVITATION,
            represented_space=locked.represented_space,
        )
    return locked


@transaction.atomic
def create_join_request(*, actor, conversation: Conversation, represented_space=None, client_reference=None):
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if locked.entry_mode != ConversationEntryMode.REQUEST:
        raise ValidationError("Cette Conversation n’accepte pas de demandes d’entrée.")
    if not context_base_eligible(actor, locked.context):
        raise PermissionDenied("Cette Conversation n’est pas disponible dans votre contexte actuel.")
    normalized_reference = (client_reference or "").strip() or None
    if normalized_reference:
        existing = ConversationJoinRequest.objects.filter(client_reference=normalized_reference).first()
        if existing:
            if existing.conversation_id == locked.pk and existing.requester_id == actor.pk:
                return existing
            raise ValidationError("Cette référence d’idempotence est déjà utilisée.")
    request = ConversationJoinRequest(
        conversation=locked,
        requester=actor,
        represented_space=represented_space,
        client_reference=normalized_reference,
        created_by=actor,
    )
    try:
        request.save()
    except IntegrityError as exc:
        raise ValidationError("Une demande d’entrée est déjà en attente.") from exc
    return request


@transaction.atomic
def respond_to_join_request(*, actor, join_request: ConversationJoinRequest, approve: bool):
    locked = ConversationJoinRequest.objects.select_for_update(of=("self",)).select_related("conversation__context").get(pk=join_request.pk)
    if not can_manage_conversation(actor, locked.conversation):
        raise PermissionDenied("Vous ne pouvez pas traiter cette demande d’entrée.")
    if locked.status != ConversationJoinRequestStatus.PENDING:
        return locked
    locked.status = ConversationJoinRequestStatus.APPROVED if approve else ConversationJoinRequestStatus.REJECTED
    locked.responded_at = timezone.now()
    locked.save(update_fields=["status", "responded_at", "updated_at"])
    if approve:
        activate_participation(
            actor=actor,
            conversation=locked.conversation,
            profile=locked.requester,
            source=ConversationParticipationSource.REQUEST,
            represented_space=locked.represented_space,
        )
    return locked


@transaction.atomic
def join_conversation(*, actor, conversation: Conversation):
    locked = Conversation.objects.select_for_update(of=("self",)).select_related("context").get(pk=conversation.pk)
    if locked.entry_mode != ConversationEntryMode.JOIN:
        raise ValidationError("Cette Conversation ne permet pas l’adhésion directe.")
    if not context_base_eligible(actor, locked.context):
        raise PermissionDenied("Cette Conversation n’est pas disponible dans votre contexte actuel.")
    return activate_participation(
        actor=actor,
        conversation=locked,
        profile=actor,
        source=ConversationParticipationSource.JOIN,
    )


@transaction.atomic
def update_personal_conversation_state(
    *, actor, conversation: Conversation, opened=False, mute=False, mute_until=None, hidden=None, archived=None, pinned=None, revisit=None
) -> ConversationUserState:
    if not can_view_conversation(actor, conversation):
        raise PermissionDenied("Cette Conversation n’est pas accessible.")
    state, _ = ConversationUserState.objects.select_for_update().get_or_create(conversation=conversation, profile=actor)
    now = timezone.now()
    if opened:
        state.last_opened_at = now
    if mute:
        state.muted_at = now
        state.muted_until = mute_until
    elif mute_until is not None:
        raise ValidationError("mute_until exige l’activation de la sourdine.")
    if hidden is not None:
        state.hidden_at = now if hidden else None
    if archived is not None:
        state.archived_at = now if archived else None
    if pinned is not None:
        state.pinned_at = now if pinned else None
    if revisit is not None:
        state.revisit_at = now if revisit else None
    state.save()
    return state

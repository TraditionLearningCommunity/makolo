"""Identifier-first Conversation invitation and collective consent orchestration.

No contact book. No name-based invitation. A Group/Space target is only a
reference to the canonical collective; its members are never copied.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.profile_visibility import ProfileVisibilityResolver
from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import Group, GroupDiscoverability, GroupStatus, GroupMembership, GroupMembershipStatus
from groups.services import can_view_group, has_group_permission
from organizations.models import Organization, SpaceLifecycle, TeamMembership, TeamMembershipStatus
from social.models import ActionNetworkBlock
from topics.models import ProfileOpenTo

from .collective_models import ConversationCollectiveAccess, ConversationCollectiveStatus
from .contact_models import ContactPolicyMode, ProfileContactPolicy
from .contact_services import profiles_blocked
from .core_models import (
    ConversationInvitation, ConversationInvitationStatus, ConversationParticipation,
    ConversationParticipationStatus, ConversationLifecycle, ConversationEntryMode,
    ConversationJoinRequest, ConversationJoinRequestStatus,
)
from .services import (
    can_manage_conversation, context_base_eligible, create_conversation_invitation,
    create_join_request, join_conversation, remove_participation, respond_to_join_request,
)

User = get_user_model()


def _identity(raw):
    if not isinstance(raw, str):
        raise ValidationError({"identifier": "Identifiant Makolo invalide."})
    identifier = raw.strip().lstrip("@").casefold()
    if not 2 <= len(identifier) <= 200 or any(ch.isspace() for ch in identifier):
        raise ValidationError({"identifier": "Saisissez un identifiant Makolo."})
    return identifier


def _context_space(conversation):
    context = conversation.context
    if context.kind == "space":
        return context.space
    if context.kind == "group":
        return context.group.space
    if context.kind == "activity":
        return context.activity.space
    if context.kind == "occurrence":
        return context.occurrence.activity.space
    if context.kind == "journey":
        return context.journey.activity.space
    return None


def _blocked_by_profile(actor, target, conversation=None):
    if profiles_blocked(actor, target):
        return True
    space = _context_space(conversation) if conversation else None
    return bool(space and ActionNetworkBlock.objects.filter(
        Q(blocker_space=space, blocked_profile=target)
        | Q(blocker_profile=target, blocked_space=space)
    ).exists())


def _blocked_collective(actor, space):
    return bool(space and ActionNetworkBlock.objects.filter(
        Q(blocker_space=space, blocked_profile=actor)
        | Q(blocker_profile=actor, blocked_space=space)
    ).exists())


def _target_can_be_invited(actor, target, conversation):
    if not target.is_active or actor.pk == target.pk or _blocked_by_profile(actor, target, conversation):
        raise ValidationError("Cette invitation n'est pas disponible.")
    policy = ProfileContactPolicy.objects.filter(profile=target).first()
    if policy and (not policy.valid_until or timezone.now() < policy.valid_until):
        if policy.mode == ContactPolicyMode.CLOSED:
            raise ValidationError("Cette invitation n'est pas disponible.")
        if policy.mode == ContactPolicyMode.CONTEXTUAL:
            kind = conversation.context.kind
            permitted = (
                (kind in {"activity", "occurrence"} and policy.allow_activity_context)
                or (kind in {"space", "group"} and policy.allow_space_context)
                or (kind == "action_proposal" and policy.allow_action_proposal_context)
                or context_base_eligible(target, conversation.context)
            )
            if not permitted:
                raise ValidationError("Cette invitation n'est pas disponible.")


def invitation_accept_allowed(actor, invitation):
    """Current eligibility hint; acceptance always rechecks inside the service."""
    conversation = invitation.conversation
    if (
        not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or invitation.invitee_id != getattr(actor, "pk", None)
        or invitation.status != ConversationInvitationStatus.PENDING
        or conversation.lifecycle != ConversationLifecycle.OPEN
        or (invitation.expires_at and invitation.expires_at <= timezone.now())
        or not invitation.created_by.is_active
        or not can_manage_conversation(invitation.created_by, conversation)
        or (invitation.represented_space_id and not can(
            actor, PermissionCode.SPACE_CONVERSATIONS_PUBLISH,
            space=invitation.represented_space,
        ))
    ):
        return False
    try:
        _target_can_be_invited(invitation.created_by, actor, conversation)
    except (ValidationError, PermissionDenied):
        return False
    return True


def _collective_manage_allowed(actor, *, space=None, group=None):
    if not getattr(actor, "is_authenticated", False) or not actor.is_active:
        return False
    if group is not None:
        return (
            group.owner_profile_id == actor.pk
            or has_group_permission(actor, PermissionCode.GROUP_CONVERSATIONS_MANAGE, group)
        )
    return bool(space is not None and can(
        actor, PermissionCode.SPACE_CONVERSATIONS_MANAGE, space=space,
    ))


def _visible_group(actor, group, *, exact=False):
    if group.status != GroupStatus.ACTIVE:
        return False
    if group.owner_profile_id == getattr(actor, "pk", None) or can_view_group(actor, group):
        return True
    if group.space_id and group.discoverability == GroupDiscoverability.SPACE_ONLY:
        return TeamMembership.objects.filter(
            team__organization_id=group.space_id, team__is_active=True,
            user=actor, status=TeamMembershipStatus.ACTIVE,
        ).exists()
    return group.discoverability in (
        {GroupDiscoverability.LISTED, GroupDiscoverability.UNLISTED}
        if exact else {GroupDiscoverability.LISTED}
    )


def _eligible_space(space):
    return space.lifecycle == SpaceLifecycle.ACTIVE


def search_invitation_candidates(*, actor, conversation, query, limit=18):
    if not can_manage_conversation(actor, conversation):
        raise PermissionDenied("Recherche réservée aux responsables.")
    text = (query or "").strip().lstrip("@")[:80]
    if len(text) < 2:
        return []
    limit = max(1, min(int(limit), 30))
    found = []
    users = User.objects.filter(
        is_active=True, profile__searchable=True,
    ).filter(
        Q(profile__public_profile=True)
        | Q(open_to_declarations__is_active=True,
            open_to_declarations__is_searchable=True),
    ).filter(
        Q(username__icontains=text)
        | Q(first_name__icontains=text)
        | Q(last_name__icontains=text)
    ).distinct().order_by("username")[:limit * 3]
    for user in users:
        if user.pk == actor.pk or _blocked_by_profile(actor, user, conversation):
            continue
        policy = ProfileContactPolicy.objects.filter(profile=user).first()
        if policy and policy.mode == ContactPolicyMode.CLOSED and (
            not policy.valid_until or policy.valid_until > timezone.now()
        ):
            continue
        visibility = ProfileVisibilityResolver(owner=user, viewer=actor)
        public_name = (user.full_name or "").strip() if (
            user.profile.public_profile and visibility.field("name")
        ) else ""
        # A private name must not act as a reverse lookup to the username.
        # Only a visible name can justify a name-only suggestion.
        username_matches = text.casefold() in user.username.casefold()
        if not username_matches and (
            not public_name or text.casefold() not in public_name.casefold()
        ):
            continue
        found.append({
            "kind": "profile", "identifier": user.username,
            "label": public_name or "Profil Makolo",
            "description": "@" + user.username,
        })
    spaces = Organization.objects.filter(
        lifecycle=SpaceLifecycle.ACTIVE, public_profile=True, searchable=True,
    ).filter(Q(slug__icontains=text) | Q(name__icontains=text)).order_by("slug")[:limit]
    for space in spaces:
        if _blocked_collective(actor, space):
            continue
        found.append({
            "kind": "space", "identifier": space.slug,
            "label": space.name, "description": "Espace · " + space.slug,
        })
    groups = Group.objects.filter(status=GroupStatus.ACTIVE).filter(
        Q(slug__icontains=text) | Q(name__icontains=text),
    ).select_related("space").order_by("slug")[:limit * 2]
    for group in groups:
        if not _visible_group(actor, group) or _blocked_collective(actor, group.space):
            continue
        found.append({
            "kind": "group", "identifier": group.slug,
            "label": group.name, "description": "Groupe · " + group.slug,
        })
    def ranking(row):
        key = row["identifier"].casefold()
        q = text.casefold()
        return (0 if key == q else 1 if key.startswith(q) else 2,
                {"profile": 0, "space": 1, "group": 2}[row["kind"]], key)
    found.sort(key=ranking)
    return found[:limit]


@transaction.atomic
def invite_identifier(*, actor, conversation, kind, identifier, client_reference=None):
    """Always resolve a canonical identifier, NEVER an ambiguous display name."""
    if not can_manage_conversation(actor, conversation):
        raise PermissionDenied("Vous ne pouvez pas inviter dans cette Conversation.")
    if conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("Cette Conversation n'est pas ouverte aux invitations.")
    if conversation.context.kind == "direct":
        raise ValidationError(
            "Une Conversation directe conserve uniquement les deux Profils consentants."
        )
    identifier = _identity(identifier)
    kind = (kind or "").strip().lower()
    if kind == "profile":
        target = User.objects.filter(is_active=True, username__iexact=identifier).first()
        if target is None:
            raise ValidationError("Cet identifiant Makolo n'est pas disponible.")
        _target_can_be_invited(actor, target, conversation)
        if ConversationParticipation.objects.filter(
            conversation=conversation, profile=target,
            status=ConversationParticipationStatus.ACTIVE,
        ).exists():
            raise ValidationError("Ce Profil participe déjà à la Conversation.")
        current = ConversationInvitation.objects.filter(
            conversation=conversation, invitee=target,
            status=ConversationInvitationStatus.PENDING,
        ).first()
        if current:
            if current.expires_at and current.expires_at <= timezone.now():
                current.status = ConversationInvitationStatus.EXPIRED
                current.responded_at = timezone.now()
                current.save(update_fields=["status", "responded_at", "updated_at"])
            else:
                return ("profile", current)
        if ConversationInvitation.objects.filter(
            conversation=conversation, invitee=target,
            status=ConversationInvitationStatus.DECLINED,
        ).exists():
            raise ValidationError("Une invitation précédente a été refusée.")
        invitation = create_conversation_invitation(
            actor=actor, conversation=conversation, invitee=target,
            client_reference=client_reference,
        )
        return ("profile", invitation)

    if conversation.context.kind in {
        "direct", "journey", "action_proposal", "dossier",
    }:
        raise ValidationError(
            "L'ajout d'un collectif n'est pas disponible pour ce contexte privé."
        )
    if kind == "space":
        space = Organization.objects.filter(slug__iexact=identifier).first()
        if not space or not _eligible_space(space) or _blocked_collective(actor, space) or not (
            (space.public_profile and space.searchable)
            or can(actor, PermissionCode.SPACE_VIEW, space=space)
        ):
            raise ValidationError("Cet identifiant Makolo n'est pas disponible.")
        target = {"space": space, "group": None}
    elif kind == "group":
        group = Group.objects.filter(slug__iexact=identifier).first()
        if not group or not _visible_group(actor, group, exact=True) or _blocked_collective(actor, group.space):
            raise ValidationError("Cet identifiant Makolo n'est pas disponible.")
        target = {"space": None, "group": group}
    else:
        raise ValidationError({"kind": "Choisissez Profil, Espace ou Groupe."})

    locked = ConversationCollectiveAccess.objects.select_for_update().filter(
        conversation=conversation,
        **{key: value for key, value in target.items() if value is not None},
    ).first()
    if locked:
        if locked.status == ConversationCollectiveStatus.PENDING and (
            locked.expires_at is None or locked.expires_at > timezone.now()
        ):
            return (kind, locked)
        if locked.status == ConversationCollectiveStatus.ACTIVE:
            return (kind, locked)
        if locked.status == ConversationCollectiveStatus.DECLINED:
            raise ValidationError("Ce collectif a déjà refusé cette invitation.")
        if locked.status == ConversationCollectiveStatus.REVOKED:
            raise ValidationError(
                "Cet accès collectif a été retiré. Une nouvelle invitation "
                "exige une procédure explicite distincte."
            )
        locked.status = ConversationCollectiveStatus.PENDING
        locked.expires_at = None
        locked.responded_at = None
        locked.responded_by = None
        locked.created_by = actor
        locked.save()
        return (kind, locked)
    link = ConversationCollectiveAccess(
        conversation=conversation, created_by=actor, **target,
    )
    try:
        link.save()
    except IntegrityError:
        raise ValidationError("Une demande pour ce collectif existe déjà.")
    return (kind, link)


@transaction.atomic
def answer_collective_invitation(*, actor, access, accept):
    locked = ConversationCollectiveAccess.objects.select_for_update().select_related(
        "space", "group", "conversation",
    ).get(pk=access.pk)
    if not _collective_manage_allowed(actor, space=locked.space, group=locked.group):
        raise PermissionDenied("Autorité de représentation insuffisante.")
    if locked.status != ConversationCollectiveStatus.PENDING:
        return locked
    now = timezone.now()
    if locked.expires_at and now >= locked.expires_at:
        locked.status = ConversationCollectiveStatus.EXPIRED
    elif locked.conversation.lifecycle != ConversationLifecycle.OPEN:
        raise ValidationError("Cette Conversation n'accepte plus d'invitations.")
    elif accept and locked.space and not _eligible_space(locked.space):
        raise ValidationError("Cet Espace est inactif.")
    elif accept and locked.group and locked.group.status != GroupStatus.ACTIVE:
        raise ValidationError("Ce Groupe est inactif.")
    else:
        locked.status = (
            ConversationCollectiveStatus.ACTIVE if accept
            else ConversationCollectiveStatus.DECLINED
        )
    locked.responded_by = actor
    locked.responded_at = now
    locked.save()
    return locked


@transaction.atomic
def revoke_collective_access(*, actor, access):
    locked = ConversationCollectiveAccess.objects.select_for_update().select_related(
        "conversation", "space", "group",
    ).get(pk=access.pk)
    if not (
        can_manage_conversation(actor, locked.conversation)
        or _collective_manage_allowed(actor, space=locked.space, group=locked.group)
    ):
        raise PermissionDenied("Vous ne pouvez pas retirer cet accès.")
    if locked.status in {ConversationCollectiveStatus.PENDING, ConversationCollectiveStatus.ACTIVE}:
        locked.status = ConversationCollectiveStatus.REVOKED
        locked.responded_at = timezone.now()
        locked.responded_by = actor
        locked.save()
    return locked


def collective_invitation_inbox(actor, *, limit=30):
    """Select pending collective consents after evaluating live authority.

    A fixed pre-authorization candidate window can hide all legitimate rows
    when many requests belong to other Spaces/Groups. Scan in DB chunks and
    stop after the actual owner-visible limit.
    """
    if (not getattr(actor, "is_authenticated", False)
            or not getattr(actor, "is_active", False)):
        return []
    # Allow one extra authorized row when an API caller needs a truthful
    # "more results" indicator without exposing an unbounded collection.
    size = max(1, min(int(limit), 51))
    now = timezone.now()
    candidates = ConversationCollectiveAccess.objects.filter(
        status=ConversationCollectiveStatus.PENDING,
        conversation__lifecycle=ConversationLifecycle.OPEN,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).select_related(
        "space", "group", "conversation__context", "created_by",
    ).order_by("-created_at", "-pk")
    visible = []
    for item in candidates.iterator(chunk_size=100):
        if not (
            (item.space is not None and _eligible_space(item.space))
            or (item.group is not None and item.group.status == GroupStatus.ACTIVE)
        ):
            continue
        if not _collective_manage_allowed(
            actor, space=item.space, group=item.group,
        ):
            continue
        visible.append(item)
        if len(visible) >= size:
            break
    return visible


def conversation_collectives_for_manager(actor, conversation):
    if not can_manage_conversation(actor, conversation):
        return []
    return [
        {
            "id": str(item.pk),
            "kind": "space" if item.space_id else "group",
            "identifier": item.space.slug if item.space_id else item.group.slug,
            "label": item.space.name if item.space_id else item.group.name,
            "status": (
                ConversationCollectiveStatus.EXPIRED
                if item.status == ConversationCollectiveStatus.PENDING
                and item.expires_at and item.expires_at <= timezone.now()
                else item.status
            ),
        }
        for item in conversation.collective_accesses.select_related(
            "space", "group",
        ).order_by("created_at")[:80]
    ]


def collective_viewer_ids(conversation):
    """Live, accepted collective members only; no membership snapshots."""
    links = conversation.collective_accesses.filter(
        status=ConversationCollectiveStatus.ACTIVE,
    ).select_related("space", "group")
    group_ids = [
        link.group_id for link in links
        if link.group_id and link.group.status == GroupStatus.ACTIVE
    ]
    space_ids = [
        link.space_id for link in links
        if link.space_id and link.space.lifecycle == SpaceLifecycle.ACTIVE
    ]
    ids = set(GroupMembership.objects.filter(
        group_id__in=group_ids, status=GroupMembershipStatus.ACTIVE,
        profile__is_active=True,
    ).values_list("profile_id", flat=True))
    ids.update(Group.objects.filter(
        pk__in=group_ids, owner_profile__is_active=True,
    ).values_list("owner_profile_id", flat=True))
    ids.update(TeamMembership.objects.filter(
        team__organization_id__in=space_ids, team__is_active=True,
        status=TeamMembershipStatus.ACTIVE, user__is_active=True,
    ).values_list("user_id", flat=True))
    return ids


def collective_access_since(profile, conversation):
    """Earliest currently valid admission to this conversation, for FROM_JOIN.

    The viewer never gains history before the collective actually accepted
    or before the Profile became a member of that collective.
    """
    if not getattr(profile, "is_active", False):
        return None
    moments = []
    links = conversation.collective_accesses.filter(
        status=ConversationCollectiveStatus.ACTIVE,
    ).select_related("space", "group")
    for link in links:
        admitted = link.responded_at or link.created_at
        if link.group_id and link.group.status == GroupStatus.ACTIVE:
            if link.group.owner_profile_id == profile.pk:
                moments.append(admitted)
            for membership in GroupMembership.objects.filter(
                group_id=link.group_id, profile=profile,
                status=GroupMembershipStatus.ACTIVE,
            ):
                moments.append(max(admitted, membership.joined_at))
        elif link.space_id and link.space.lifecycle == SpaceLifecycle.ACTIVE:
            for membership in TeamMembership.objects.filter(
                team__organization_id=link.space_id,
                team__is_active=True, user=profile,
                status=TeamMembershipStatus.ACTIVE,
            ):
                moments.append(max(admitted, membership.joined_at or membership.created_at))
    return min(moments) if moments else None


def profile_conversation_since(profile, conversation):
    """Oldest current explicit or collectively accepted access (or none)."""
    direct = ConversationParticipation.objects.filter(
        conversation=conversation, profile=profile,
        status=ConversationParticipationStatus.ACTIVE,
    ).values_list("joined_at", flat=True).first()
    derived = collective_access_since(profile, conversation)
    return min(x for x in (direct, derived) if x is not None) if (
        direct is not None or derived is not None
    ) else None

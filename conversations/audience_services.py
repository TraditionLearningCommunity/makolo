from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from activities.involvement_models import ActivityInvolvement, ActivityInvolvementStatus
from activities.participant_selectors import activity_participant_ids, occurrence_participant_ids
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from groups.models import GroupMembership, GroupMembershipStatus
from organizations.models import TeamMembership, TeamMembershipStatus

from .audience_models import (
    ConversationAudienceRule,
    ConversationAudienceRuleKind,
    ConversationAudienceRuleOperation,
    ConversationAudienceSet,
    ConversationAudienceStatus,
)
from .core_models import ConversationContextKind, ConversationParticipation, ConversationParticipationStatus
from .services import can_manage_conversation


User = get_user_model()


def _current_mandates(at=None):
    at = at or timezone.now()
    return Mandate.objects.filter(
        status=MandateStatus.ACTIVE,
        revoked_at__isnull=True,
        role__is_active=True,
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=at),
        Q(valid_until__isnull=True) | Q(valid_until__gt=at),
    )


def _profiles_with_permission(*, permission_code, scope_type, target_field, target_id, at=None):
    if not target_id:
        return set()
    return set(
        _current_mandates(at)
        .filter(
            scope_type=scope_type,
            **{target_field: target_id},
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        )
        .values_list("profile_id", flat=True)
        .distinct()
    )


def conversation_manager_ids(conversation, *, at=None):
    """Profiles with current manage authority for this Conversation context."""

    context = conversation.context
    ids = set(User.objects.filter(is_superuser=True, is_active=True).values_list("id", flat=True))

    if context.kind == ConversationContextKind.SPACE:
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
            scope_type=AuthorityScope.SPACE,
            target_field="space_id",
            target_id=context.space_id,
            at=at,
        )
    elif context.kind == ConversationContextKind.GROUP:
        if context.group.owner_profile_id:
            ids.add(context.group.owner_profile_id)
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.GROUP_CONVERSATIONS_MANAGE,
            scope_type=AuthorityScope.GROUP,
            target_field="group_id",
            target_id=context.group_id,
            at=at,
        )
        if context.group.space_id:
            ids |= _profiles_with_permission(
                permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
                scope_type=AuthorityScope.SPACE,
                target_field="space_id",
                target_id=context.group.space_id,
                at=at,
            )
    elif context.kind in {ConversationContextKind.ACTIVITY, ConversationContextKind.OCCURRENCE}:
        activity = context.activity if context.kind == ConversationContextKind.ACTIVITY else context.occurrence.activity
        if activity.owner_profile_id:
            ids.add(activity.owner_profile_id)
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.ACTIVITY_CONVERSATIONS_MANAGE,
            scope_type=AuthorityScope.ACTIVITY,
            target_field="activity_id",
            target_id=activity.pk,
            at=at,
        )
        if activity.space_id:
            ids |= _profiles_with_permission(
                permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
                scope_type=AuthorityScope.SPACE,
                target_field="space_id",
                target_id=activity.space_id,
                at=at,
            )
    elif context.kind == ConversationContextKind.DOSSIER:
        if context.dossier.owner_profile_id:
            ids.add(context.dossier.owner_profile_id)
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.DOSSIER_CONVERSATIONS_MANAGE,
            scope_type=AuthorityScope.DOSSIER,
            target_field="dossier_id",
            target_id=context.dossier_id,
            at=at,
        )
        if context.dossier.owning_space_id:
            ids |= _profiles_with_permission(
                permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
                scope_type=AuthorityScope.SPACE,
                target_field="space_id",
                target_id=context.dossier.owning_space_id,
                at=at,
            )
    elif context.kind == ConversationContextKind.PROJECT:
        if context.project.owner_profile_id:
            ids.add(context.project.owner_profile_id)
        if context.project.owning_space_id:
            ids |= _profiles_with_permission(
                permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
                scope_type=AuthorityScope.SPACE,
                target_field="space_id",
                target_id=context.project.owning_space_id,
                at=at,
            )
    elif context.kind == ConversationContextKind.JOURNEY:
        journey = context.journey
        ids.update(filter(None, (journey.beneficiary_id, journey.initiated_by_id)))
        activity = journey.activity
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.ACTIVITY_CONVERSATIONS_MANAGE,
            scope_type=AuthorityScope.ACTIVITY,
            target_field="activity_id",
            target_id=activity.pk,
            at=at,
        )
        if activity.space_id:
            ids |= _profiles_with_permission(
                permission_code=PermissionCode.SPACE_CONVERSATIONS_MANAGE,
                scope_type=AuthorityScope.SPACE,
                target_field="space_id",
                target_id=activity.space_id,
                at=at,
            )
    elif context.kind == ConversationContextKind.ACTION_PROPOSAL:
        proposal = context.action_proposal
        ids |= action_proposal_party_ids(proposal, at=at)
    elif context.kind == ConversationContextKind.DIRECT:
        ids.update((context.direct_profile_a_id, context.direct_profile_b_id))

    return set(User.objects.filter(pk__in=ids, is_active=True).values_list("id", flat=True))


def action_proposal_party_ids(proposal, *, at=None):
    ids = set(filter(None, (
        proposal.need.owner_profile_id,
        proposal.candidate_profile_id,
        proposal.initiated_by_id,
        proposal.responded_by_id,
    )))
    if proposal.need.space_id:
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.SPACE_ACTION_NETWORK_MANAGE,
            scope_type=AuthorityScope.SPACE,
            target_field="space_id",
            target_id=proposal.need.space_id,
            at=at,
        )
    if proposal.candidate_space_id:
        ids |= _profiles_with_permission(
            permission_code=PermissionCode.SPACE_ACTION_NETWORK_MANAGE,
            scope_type=AuthorityScope.SPACE,
            target_field="space_id",
            target_id=proposal.candidate_space_id,
            at=at,
        )
    return set(User.objects.filter(pk__in=ids, is_active=True).values_list("id", flat=True))


def _involvement_profile_ids(*, activity, occurrence=None, function_kind=None):
    qs = ActivityInvolvement.objects.filter(
        activity=activity,
        profile__isnull=False,
        status=ActivityInvolvementStatus.ACTIVE,
    )
    if occurrence is not None:
        qs = qs.filter(Q(occurrence=occurrence) | Q(occurrence__isnull=True))
    if function_kind:
        qs = qs.filter(functions__kind=function_kind)
    return set(qs.values_list("profile_id", flat=True).distinct())


def conversation_viewer_ids(conversation, *, at=None):
    """Live derived viewer candidates; no copied recipient rows are authoritative."""

    context = conversation.context
    ids = set(
        ConversationParticipation.objects.filter(
            conversation=conversation,
            status=ConversationParticipationStatus.ACTIVE,
        ).values_list("profile_id", flat=True)
    )
    ids |= conversation_manager_ids(conversation, at=at)

    if context.kind == ConversationContextKind.SPACE:
        ids |= set(
            TeamMembership.objects.filter(
                team__organization=context.space,
                status=TeamMembershipStatus.ACTIVE,
            ).values_list("user_id", flat=True)
        )
    elif context.kind == ConversationContextKind.GROUP:
        ids |= set(
            GroupMembership.objects.filter(
                group=context.group,
                status=GroupMembershipStatus.ACTIVE,
            ).values_list("profile_id", flat=True)
        )
    elif context.kind == ConversationContextKind.ACTIVITY:
        ids |= activity_participant_ids(context.activity)
        ids |= _involvement_profile_ids(activity=context.activity)
    elif context.kind == ConversationContextKind.OCCURRENCE:
        ids |= occurrence_participant_ids(context.occurrence)
        ids |= _involvement_profile_ids(activity=context.occurrence.activity, occurrence=context.occurrence)
    elif context.kind == ConversationContextKind.JOURNEY:
        ids.update(filter(None, (context.journey.beneficiary_id, context.journey.initiated_by_id)))
    elif context.kind == ConversationContextKind.ACTION_PROPOSAL:
        ids |= action_proposal_party_ids(context.action_proposal, at=at)
    elif context.kind == ConversationContextKind.DIRECT:
        ids.update((context.direct_profile_a_id, context.direct_profile_b_id))

    return set(User.objects.filter(pk__in=ids, is_active=True).values_list("id", flat=True))


def _rule_profile_ids(rule, *, at=None):
    conversation = rule.audience_set.conversation
    if rule.kind == ConversationAudienceRuleKind.ALL_CONVERSATION_VIEWERS:
        return conversation_viewer_ids(conversation, at=at)
    if rule.kind == ConversationAudienceRuleKind.EXPLICIT_PROFILE:
        return {rule.profile_id} if rule.profile_id and rule.profile.is_active else set()
    if rule.kind == ConversationAudienceRuleKind.CONVERSATION_PARTICIPANTS:
        return set(
            ConversationParticipation.objects.filter(
                conversation=conversation,
                status=ConversationParticipationStatus.ACTIVE,
                profile__is_active=True,
            ).values_list("profile_id", flat=True)
        )
    if rule.kind == ConversationAudienceRuleKind.CONVERSATION_MANAGERS:
        return conversation_manager_ids(conversation, at=at)
    if rule.kind == ConversationAudienceRuleKind.GROUP_MEMBERS:
        return set(
            GroupMembership.objects.filter(
                group=rule.group,
                status=GroupMembershipStatus.ACTIVE,
                profile__is_active=True,
            ).values_list("profile_id", flat=True)
        )
    if rule.kind == ConversationAudienceRuleKind.OCCURRENCE_PARTICIPANTS:
        return occurrence_participant_ids(rule.occurrence)
    if rule.kind == ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION:
        qs = ActivityInvolvement.objects.filter(
            activity=rule.activity,
            profile__isnull=False,
            profile__is_active=True,
            status=ActivityInvolvementStatus.ACTIVE,
            functions__kind=rule.involvement_function_kind,
        )
        if rule.occurrence_id:
            qs = qs.filter(Q(occurrence=rule.occurrence) | Q(occurrence__isnull=True))
        return set(qs.values_list("profile_id", flat=True).distinct())
    if rule.kind == ConversationAudienceRuleKind.ACTION_PROPOSAL_PARTIES:
        return action_proposal_party_ids(rule.action_proposal, at=at)
    return set()


def resolve_audience_ids(audience_set: ConversationAudienceSet, *, at=None):
    if audience_set.status != ConversationAudienceStatus.ACTIVE:
        return set()
    include = set()
    exclude = set()
    rules = audience_set.rules.select_related(
        "profile", "group", "activity", "occurrence", "action_proposal__need"
    ).all()
    for rule in rules:
        values = _rule_profile_ids(rule, at=at)
        if rule.operation == ConversationAudienceRuleOperation.INCLUDE:
            include |= values
        else:
            exclude |= values
    # Audience rules can narrow a Conversation, never grant access outside its live boundary.
    return (include - exclude) & conversation_viewer_ids(audience_set.conversation, at=at)


def profile_in_audience(profile, audience_set: ConversationAudienceSet, *, at=None) -> bool:
    if not getattr(profile, "is_authenticated", False) or not getattr(profile, "is_active", False):
        return False
    return profile.pk in resolve_audience_ids(audience_set, at=at)


@transaction.atomic
def create_audience_set(*, actor, conversation, label):
    if not can_manage_conversation(actor, conversation):
        raise PermissionDenied("Vous ne pouvez pas gérer les audiences de cette Conversation.")
    audience = ConversationAudienceSet(conversation=conversation, label=label, created_by=actor)
    audience.save()
    return audience


@transaction.atomic
def add_audience_rule(*, actor, audience_set, operation, kind, **targets):
    if audience_set.status != ConversationAudienceStatus.ACTIVE:
        raise ValidationError("Cette audience est retirée.")
    if not can_manage_conversation(actor, audience_set.conversation):
        raise PermissionDenied("Vous ne pouvez pas modifier cette audience.")
    rule = ConversationAudienceRule(
        audience_set=audience_set,
        operation=operation,
        kind=kind,
        profile=targets.get("profile"),
        group=targets.get("group"),
        activity=targets.get("activity"),
        occurrence=targets.get("occurrence"),
        action_proposal=targets.get("action_proposal"),
        involvement_function_kind=targets.get("involvement_function_kind", ""),
    )
    rule.save()
    return rule

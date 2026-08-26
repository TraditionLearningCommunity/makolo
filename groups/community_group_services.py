from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can

from .models import (
    GroupDiscoverability,
    GroupMembershipPolicy,
    GroupVisibility,
)
from .services import create_group, has_group_permission, update_group


def _legacy_visibility(*, space, discoverability):
    if space is not None and discoverability == GroupDiscoverability.SPACE_ONLY:
        return GroupVisibility.SPACE
    return GroupVisibility.PRIVATE


@transaction.atomic
def create_community_group(
    *,
    actor,
    name,
    description="",
    space=None,
    discoverability=GroupDiscoverability.HIDDEN,
    membership_policy=GroupMembershipPolicy.INVITE_ONLY,
):
    if space is not None and not can(actor, PermissionCode.SPACE_GROUPS_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas créer de Groupe dans cet Espace.")
    if space is None and discoverability == GroupDiscoverability.SPACE_ONLY:
        raise ValidationError(
            {"discoverability": "Un Groupe personnel ne peut pas être limité à un Espace."}
        )
    group = create_group(
        actor=actor,
        name=name,
        description=description,
        space=space,
        visibility=_legacy_visibility(space=space, discoverability=discoverability),
    )
    group.discoverability = discoverability
    group.membership_policy = membership_policy
    group.full_clean()
    group.save(
        update_fields=[
            "discoverability",
            "membership_policy",
            "updated_at",
        ]
    )
    return group


@transaction.atomic
def update_community_group(
    *,
    actor,
    group,
    name,
    description="",
    discoverability,
    membership_policy,
):
    if not has_group_permission(actor, PermissionCode.GROUP_MANAGE, group):
        raise PermissionDenied("Vous ne pouvez pas modifier ce Groupe.")
    if group.space_id is None and discoverability == GroupDiscoverability.SPACE_ONLY:
        raise ValidationError(
            {"discoverability": "Un Groupe personnel ne peut pas être limité à un Espace."}
        )
    group = update_group(
        actor=actor,
        group=group,
        name=name,
        description=description,
        visibility=_legacy_visibility(
            space=group.space,
            discoverability=discoverability,
        ),
    )
    group.discoverability = discoverability
    group.membership_policy = membership_policy
    group.full_clean()
    group.save(
        update_fields=[
            "discoverability",
            "membership_policy",
            "updated_at",
        ]
    )
    return group

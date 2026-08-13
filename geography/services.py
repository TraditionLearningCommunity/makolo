from django.core.exceptions import PermissionDenied
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can

from .models import Place, SpacePlace


def require_space_place_permission(actor, organization, permission_code):
    if not can(actor, permission_code, organization):
        raise PermissionDenied("Vous n'avez pas l'autorisation requise sur les Lieux de cet Espace.")


@transaction.atomic
def attach_place_to_space(
    *,
    actor,
    organization,
    place,
    role,
    public_label="",
    is_primary=False,
    is_public=False,
    is_active=True,
    position=0,
):
    require_space_place_permission(actor, organization, PermissionCode.SPACE_PLACES_MANAGE)
    if is_primary:
        SpacePlace.objects.filter(
            organization=organization,
            role=role,
            is_active=True,
            is_primary=True,
        ).update(is_primary=False)
    relation = SpacePlace(
        organization=organization,
        place=place,
        role=role,
        public_label=public_label,
        is_primary=is_primary,
        is_public=is_public,
        is_active=is_active,
        position=position,
    )
    relation.full_clean()
    relation.save()
    return relation


@transaction.atomic
def create_place_for_space(*, actor, organization, place_data, relation_data):
    require_space_place_permission(actor, organization, PermissionCode.SPACE_PLACES_MANAGE)
    place = Place(created_by=actor, **place_data)
    place.full_clean()
    place.save()
    relation = attach_place_to_space(
        actor=actor,
        organization=organization,
        place=place,
        **relation_data,
    )
    return relation


@transaction.atomic
def update_space_place(*, actor, relation, **fields):
    relation = SpacePlace.objects.select_for_update().select_related("organization", "place").get(pk=relation.pk)
    require_space_place_permission(actor, relation.organization, PermissionCode.SPACE_PLACES_MANAGE)
    allowed = {"role", "public_label", "is_primary", "is_public", "is_active", "position"}
    for field, value in fields.items():
        if field in allowed:
            setattr(relation, field, value)
    if relation.is_primary:
        relation.is_active = True
        SpacePlace.objects.filter(
            organization=relation.organization,
            role=relation.role,
            is_active=True,
            is_primary=True,
        ).exclude(pk=relation.pk).update(is_primary=False)
    relation.full_clean()
    relation.save()
    return relation


@transaction.atomic
def deactivate_space_place(*, actor, relation):
    relation = SpacePlace.objects.select_for_update().select_related("organization").get(pk=relation.pk)
    require_space_place_permission(actor, relation.organization, PermissionCode.SPACE_PLACES_MANAGE)
    relation.is_active = False
    relation.is_primary = False
    relation.save(update_fields=["is_active", "is_primary", "updated_at"])
    return relation

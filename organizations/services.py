from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Organization, OrganizationMembership, OrganizationRole
from .permissions import user_can_manage_organization


User = get_user_model()


@transaction.atomic
def create_organization(*, creator, name: str, **fields) -> Organization:
    if not getattr(creator, "is_authenticated", False):
        raise PermissionDenied("Vous devez être connecté pour créer une organisation.")
    organization = Organization(created_by=creator, name=name.strip(), **fields)
    organization.full_clean()
    organization.save()
    OrganizationMembership.objects.create(
        organization=organization,
        user=creator,
        role=OrganizationRole.OWNER,
        invited_by=creator,
    )
    return organization


@transaction.atomic
def add_or_update_member(*, organization, actor, user, role: str) -> OrganizationMembership:
    if not user_can_manage_organization(actor, organization):
        raise PermissionDenied("Vous ne pouvez pas gérer l'équipe de cette organisation.")
    if role not in OrganizationRole.values:
        raise ValidationError("Rôle d'organisation invalide.")
    membership, _ = OrganizationMembership.objects.update_or_create(
        organization=organization,
        user=user,
        defaults={
            "role": role,
            "is_active": True,
            "invited_by": actor,
        },
    )
    membership.full_clean()
    membership.save()
    return membership


@transaction.atomic
def deactivate_member(*, membership, actor) -> OrganizationMembership:
    membership = OrganizationMembership.objects.select_for_update().select_related(
        "organization", "user"
    ).get(pk=membership.pk)
    if not user_can_manage_organization(actor, membership.organization):
        raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
    if membership.user_id == actor.pk and membership.role == OrganizationRole.OWNER:
        raise ValidationError("Le propriétaire actif ne peut pas se retirer lui-même de cette façon.")
    if membership.role == OrganizationRole.OWNER and not OrganizationMembership.objects.filter(
        organization=membership.organization,
        role=OrganizationRole.OWNER,
        is_active=True,
    ).exclude(pk=membership.pk).exists():
        raise ValidationError("Une organisation doit conserver au moins un propriétaire actif.")
    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    return membership


def find_user_for_team(*, email: str):
    email = email.strip().lower()
    if not email:
        raise ValidationError("L'adresse e-mail est obligatoire.")
    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist as exc:
        raise ValidationError(
            "Aucun compte Makolo ne correspond à cette adresse e-mail."
        ) from exc

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Organization, OrganizationFollow, OrganizationMembership, OrganizationRole
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
def ensure_personal_organization(user) -> Organization:
    membership = (
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization")
        .order_by("joined_at")
        .first()
    )
    if membership:
        return membership.organization
    display = getattr(user, "full_name", "") or user.username or user.email.split("@")[0]
    return create_organization(
        creator=user,
        name=f"{display} Events",
        contact_email=user.email or "",
        public_profile=True,
    )


@transaction.atomic
def add_or_update_member(*, organization, actor, user, role: str) -> OrganizationMembership:
    if not user_can_manage_organization(actor, organization):
        raise PermissionDenied("Vous ne pouvez pas gérer l'équipe de cette organisation.")
    if role not in OrganizationRole.values:
        raise ValidationError("Rôle d'organisation invalide.")
    membership, _ = OrganizationMembership.objects.update_or_create(
        organization=organization,
        user=user,
        defaults={"role": role, "is_active": True, "invited_by": actor},
    )
    membership.full_clean()
    membership.save()
    return membership


@transaction.atomic
def deactivate_member(*, membership, actor) -> OrganizationMembership:
    membership = OrganizationMembership.objects.select_for_update().select_related("organization", "user").get(pk=membership.pk)
    if not user_can_manage_organization(actor, membership.organization):
        raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
    if membership.user_id == actor.pk and membership.role == OrganizationRole.OWNER:
        raise ValidationError("Le propriétaire actif ne peut pas se retirer lui-même de cette façon.")
    if membership.role == OrganizationRole.OWNER and not OrganizationMembership.objects.filter(
        organization=membership.organization, role=OrganizationRole.OWNER, is_active=True
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
        raise ValidationError("Aucun compte Makolo ne correspond à cette adresse e-mail.") from exc


def _sync_follower_to_crm_on_commit(follow_id):
    def callback():
        from crm.services import sync_contact_from_follower

        follow = OrganizationFollow.objects.select_related("organization", "user").filter(pk=follow_id).first()
        if follow:
            sync_contact_from_follower(follow)

    transaction.on_commit(callback)


@transaction.atomic
def follow_organization(*, user, organization: Organization, **preferences) -> OrganizationFollow:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour suivre un organisateur.")
    if not organization.public_profile or organization.verification_status == "suspended":
        raise ValidationError("Cet organisateur ne peut pas être suivi actuellement.")
    allowed = {
        "notify_new_events",
        "notify_announcements",
        "email_new_events",
        "email_announcements",
    }
    defaults = {key: bool(value) for key, value in preferences.items() if key in allowed}
    follow, _ = OrganizationFollow.objects.update_or_create(
        organization=organization,
        user=user,
        defaults=defaults,
    )
    _sync_follower_to_crm_on_commit(follow.pk)
    return follow


@transaction.atomic
def update_follow_preferences(*, follow: OrganizationFollow, user, **preferences) -> OrganizationFollow:
    follow = OrganizationFollow.objects.select_for_update().select_related("organization", "user").get(pk=follow.pk)
    if follow.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Vous ne pouvez modifier que vos propres abonnements.")
    allowed = {
        "notify_new_events",
        "notify_announcements",
        "email_new_events",
        "email_announcements",
    }
    changed = []
    for key, value in preferences.items():
        if key in allowed:
            setattr(follow, key, bool(value))
            changed.append(key)
    if changed:
        follow.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
        _sync_follower_to_crm_on_commit(follow.pk)
    return follow


@transaction.atomic
def unfollow_organization(*, follow: OrganizationFollow, user) -> None:
    follow = OrganizationFollow.objects.select_for_update().get(pk=follow.pk)
    if follow.user_id != getattr(user, "pk", None):
        raise PermissionDenied("Vous ne pouvez supprimer que vos propres abonnements.")
    organization_id = follow.organization_id
    user_id = follow.user_id
    follow.delete()

    def revoke():
        from crm.services import revoke_follower_consent

        revoke_follower_consent(organization_id=organization_id, user_id=user_id)

    transaction.on_commit(revoke)

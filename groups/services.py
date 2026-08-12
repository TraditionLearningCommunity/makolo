from __future__ import annotations

import csv
import hashlib
import hmac
import io
import logging
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import (
    can,
    get_system_role,
    grant_group_role,
    replace_standard_group_role,
    revoke_mandate,
)

from .models import (
    Group,
    GroupInvitation,
    GroupInvitationStatus,
    GroupMembership,
    GroupMembershipSource,
    GroupMembershipStatus,
    GroupSnapshot,
    GroupSnapshotMember,
    GroupStatus,
    GroupVisibility,
)


logger = logging.getLogger("makolo")
User = get_user_model()
IMPORT_MAX_ROWS = 1000
INVITATION_TTL = timedelta(days=7)
INVITATION_VERIFICATION_TTL = timedelta(minutes=15)

_GROUP_MANAGEMENT_CODES = {
    PermissionCode.GROUP_MANAGE,
    PermissionCode.GROUP_MEMBERS_MANAGE,
    PermissionCode.GROUP_INVITATIONS_MANAGE,
    PermissionCode.GROUP_SNAPSHOTS_CREATE,
    PermissionCode.GROUP_OWNERSHIP_MANAGE,
}


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    prefix = "+" if raw.startswith("+") else ""
    digits = "".join(character for character in raw if character.isdigit())
    return f"{prefix}{digits}" if digits else ""


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verification_digest(invitation_id, code: str) -> str:
    payload = f"{invitation_id}:{code}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _new_invitation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, _token_digest(token)


def _lock_group(group_or_pk) -> Group:
    pk = getattr(group_or_pk, "pk", group_or_pk)
    return Group.objects.select_for_update().order_by().get(pk=pk)


def has_group_permission(profile, permission_code: str, group: Group) -> bool:
    """Resolve direct Groupe authority, then the explicit Espace inheritance rule."""
    if can(profile, permission_code, group=group):
        return True
    if not group.space_id:
        return False
    if permission_code in _GROUP_MANAGEMENT_CODES:
        return can(profile, PermissionCode.SPACE_GROUPS_MANAGE, group.space)
    if permission_code in {PermissionCode.GROUP_VIEW, PermissionCode.GROUP_MEMBERS_VIEW}:
        return can(profile, PermissionCode.SPACE_GROUPS_VIEW, group.space) or can(
            profile,
            PermissionCode.SPACE_GROUPS_MANAGE,
            group.space,
        )
    return False


def require_group_permission(profile, permission_code: str, group: Group) -> None:
    if not has_group_permission(profile, permission_code, group):
        raise PermissionDenied("Vous n'avez pas l'autorisation requise sur ce Groupe.")


def can_view_group(profile, group: Group) -> bool:
    if has_group_permission(profile, PermissionCode.GROUP_VIEW, group):
        return True
    if not getattr(profile, "is_authenticated", False):
        return False
    return GroupMembership.objects.filter(
        group=group,
        profile=profile,
        status=GroupMembershipStatus.ACTIVE,
    ).exists()


@transaction.atomic
def create_group(
    *,
    actor,
    name: str,
    description: str = "",
    space=None,
    visibility=GroupVisibility.PRIVATE,
) -> Group:
    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": "Le nom du Groupe est obligatoire."})
    if space is not None:
        if not can(actor, PermissionCode.SPACE_GROUPS_MANAGE, space):
            raise PermissionDenied("Vous ne pouvez pas créer de Groupe dans cet Espace.")
        group = Group(
            name=name,
            description=(description or "").strip(),
            space=space,
            owner_profile=None,
            created_by=actor,
            visibility=visibility,
        )
    else:
        group = Group(
            name=name,
            description=(description or "").strip(),
            owner_profile=actor,
            created_by=actor,
            visibility=GroupVisibility.PRIVATE,
        )
    group.full_clean()
    group.save()
    if group.owner_profile_id:
        grant_group_role(
            profile=actor,
            group=group,
            role=SystemRoleCode.GROUP_OWNER,
            granted_by=actor,
            source="group-create",
        )
    return group


@transaction.atomic
def update_group(*, actor, group, name: str, description: str = "", visibility=None) -> Group:
    locked = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MANAGE, locked)
    locked.name = (name or "").strip()
    locked.description = (description or "").strip()
    if visibility is not None:
        locked.visibility = visibility
    locked.full_clean()
    locked.save(update_fields=["name", "description", "visibility", "updated_at"])
    return locked


@transaction.atomic
def archive_group(*, actor, group) -> Group:
    locked = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MANAGE, locked)
    if locked.status == GroupStatus.ARCHIVED:
        return locked
    locked.status = GroupStatus.ARCHIVED
    locked.save(update_fields=["status", "updated_at"])
    return locked


@transaction.atomic
def add_member(
    *,
    actor,
    group,
    profile,
    external_reference: str = "",
    source=GroupMembershipSource.MANUAL,
    reactivate: bool = True,
) -> tuple[GroupMembership, bool]:
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Un Groupe archivé n'accepte plus de nouveaux membres.")
    external_reference = (external_reference or "").strip()
    if external_reference:
        conflict = GroupMembership.objects.filter(
            group=locked_group,
            external_reference=external_reference,
        ).exclude(profile=profile).exists()
        if conflict:
            raise ValidationError(
                {"external_reference": "Cette référence externe appartient déjà à un autre membre du Groupe."}
            )

    membership = (
        GroupMembership.objects.select_for_update()
        .filter(group=locked_group, profile=profile)
        .order_by()
        .first()
    )
    if membership:
        if membership.status == GroupMembershipStatus.ACTIVE:
            changed = []
            if external_reference and membership.external_reference != external_reference:
                membership.external_reference = external_reference
                changed.append("external_reference")
            if changed:
                membership.save(update_fields=changed + ["updated_at"])
            return membership, False
        if not reactivate:
            raise ValidationError("Cette personne possède déjà un historique d'appartenance non actif.")
        membership.status = GroupMembershipStatus.ACTIVE
        membership.source = source
        membership.joined_at = timezone.now()
        membership.verified_at = timezone.now()
        if external_reference:
            membership.external_reference = external_reference
        membership.save(
            update_fields=[
                "status",
                "source",
                "joined_at",
                "verified_at",
                "external_reference",
                "updated_at",
            ]
        )
        return membership, False

    membership = GroupMembership(
        group=locked_group,
        profile=profile,
        status=GroupMembershipStatus.ACTIVE,
        source=source,
        external_reference=external_reference,
        verified_at=timezone.now(),
    )
    membership.full_clean()
    membership.save()
    return membership, True


@transaction.atomic
def suspend_member(*, actor, group, profile) -> GroupMembership:
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group)
    membership = GroupMembership.objects.select_for_update().filter(
        group=locked_group,
        profile=profile,
    ).order_by().first()
    if not membership:
        raise ValidationError("Cette personne n'appartient pas au Groupe.")
    if membership.status != GroupMembershipStatus.SUSPENDED:
        membership.status = GroupMembershipStatus.SUSPENDED
        membership.save(update_fields=["status", "updated_at"])
    return membership


@transaction.atomic
def remove_member(*, actor, group, profile) -> GroupMembership:
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group)
    membership = GroupMembership.objects.select_for_update().filter(
        group=locked_group,
        profile=profile,
    ).order_by().first()
    if not membership:
        raise ValidationError("Cette personne n'appartient pas au Groupe.")
    if membership.status != GroupMembershipStatus.REMOVED:
        membership.status = GroupMembershipStatus.REMOVED
        membership.save(update_fields=["status", "updated_at"])
    return membership


@transaction.atomic
def leave_group(*, profile, group) -> GroupMembership:
    locked_group = _lock_group(group)
    membership = GroupMembership.objects.select_for_update().filter(
        group=locked_group,
        profile=profile,
    ).order_by().first()
    if not membership or membership.status != GroupMembershipStatus.ACTIVE:
        raise ValidationError("Vous n'êtes pas membre actif de ce Groupe.")
    membership.status = GroupMembershipStatus.LEFT
    membership.save(update_fields=["status", "updated_at"])
    return membership


def _resolve_profile_for_identity(*, email="", phone=""):
    email = normalize_email(email)
    phone = normalize_phone(phone)
    by_email = User.objects.filter(email__iexact=email).first() if email else None
    phone_matches = list(User.objects.filter(phone=phone)[:2]) if phone else []
    if len(phone_matches) > 1:
        raise ValidationError({"phone": "Plusieurs Profils correspondent à ce téléphone; aucun choix automatique n'est sûr."})
    by_phone = phone_matches[0] if phone_matches else None
    if by_email and by_phone and by_email.pk != by_phone.pk:
        raise ValidationError("L'e-mail et le téléphone correspondent à deux Profils différents.")
    return by_email or by_phone


def _send_invitation_email(invitation_id, raw_token):
    try:
        invitation = GroupInvitation.objects.select_related("group").get(pk=invitation_id)
        if not invitation.email:
            return
        path = reverse("groups:invitation", kwargs={"token": raw_token})
        url = f"{settings.MAKOLO_PUBLIC_BASE_URL}{path}"
        mail.send_mail(
            subject=f"Makolo — Invitation au Groupe {invitation.group.name}",
            message=(
                f"Vous êtes invité·e à rejoindre le Groupe « {invitation.group.name} » sur Makolo.\n\n"
                f"Ouvrez ce lien puis connectez-vous avec l'identité invitée :\n{url}\n\n"
                "Ce lien est personnel, à usage unique et expire automatiquement."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Group invitation email delivery failed invitation_id=%s", invitation_id)


def _send_invitation_verification_email(invitation_id, code):
    try:
        invitation = GroupInvitation.objects.get(pk=invitation_id)
        if not invitation.email:
            return
        mail.send_mail(
            subject="Makolo — Vérification de votre invitation Groupe",
            message=(
                "Une vérification d'identité a été demandée pour rejoindre un Groupe Makolo.\n\n"
                f"Code de vérification : {code}\n\n"
                "Ce code expire dans 15 minutes. Ne le transmettez pas avec le lien d'invitation."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Group invitation verification delivery failed invitation_id=%s", invitation_id)


def _create_or_refresh_invitation_locked(
    *,
    group,
    invited_by,
    profile=None,
    email="",
    phone="",
    external_reference="",
    first_name="",
    last_name="",
    send_email=True,
):
    email = normalize_email(email)
    phone = normalize_phone(phone)
    external_reference = (external_reference or "").strip()
    if profile is None and (email or phone):
        profile = _resolve_profile_for_identity(email=email, phone=phone)
    if not any((profile, email, phone, external_reference)):
        raise ValidationError("Une invitation doit cibler une identité.")
    if profile and GroupMembership.objects.filter(
        group=group,
        profile=profile,
        status=GroupMembershipStatus.ACTIVE,
    ).exists():
        raise ValidationError("Ce Profil est déjà membre actif du Groupe.")

    pending = GroupInvitation.objects.select_for_update().filter(
        group=group,
        status=GroupInvitationStatus.PENDING,
    ).order_by()
    if profile is not None:
        pending = pending.filter(profile=profile)
    elif email:
        pending = pending.filter(email__iexact=email)
    elif phone:
        pending = pending.filter(phone=phone)
    else:
        pending = pending.filter(external_reference=external_reference)
    invitation = pending.first()
    raw_token, digest = _new_invitation_token()
    expires_at = timezone.now() + INVITATION_TTL
    if invitation:
        invitation.profile = profile
        invitation.email = email
        invitation.phone = phone
        invitation.external_reference = external_reference
        invitation.first_name = (first_name or "").strip()
        invitation.last_name = (last_name or "").strip()
        invitation.invited_by = invited_by
        invitation.expires_at = expires_at
        invitation.token_digest = digest
        invitation.verification_digest = ""
        invitation.verification_expires_at = None
        invitation.identity_verified_at = None
        invitation.save()
    else:
        invitation = GroupInvitation(
            group=group,
            profile=profile,
            email=email,
            phone=phone,
            external_reference=external_reference,
            first_name=(first_name or "").strip(),
            last_name=(last_name or "").strip(),
            invited_by=invited_by,
            expires_at=expires_at,
            token_digest=digest,
        )
        invitation.full_clean()
        invitation.save()
    if send_email and invitation.email:
        transaction.on_commit(
            lambda invitation_id=invitation.pk, token=raw_token: _send_invitation_email(
                invitation_id,
                token,
            )
        )
    return invitation, raw_token


@transaction.atomic
def invite_member(
    *,
    actor,
    group,
    profile=None,
    email="",
    phone="",
    external_reference="",
    first_name="",
    last_name="",
) -> tuple[GroupInvitation, str]:
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_INVITATIONS_MANAGE, locked_group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Un Groupe archivé n'accepte plus d'invitations.")
    return _create_or_refresh_invitation_locked(
        group=locked_group,
        invited_by=actor,
        profile=profile,
        email=email,
        phone=phone,
        external_reference=external_reference,
        first_name=first_name,
        last_name=last_name,
    )


@transaction.atomic
def link_invitation_profile(*, actor, invitation, profile) -> GroupInvitation:
    locked_group = _lock_group(invitation.group_id)
    require_group_permission(actor, PermissionCode.GROUP_INVITATIONS_MANAGE, locked_group)
    locked = GroupInvitation.objects.select_for_update().order_by().get(pk=invitation.pk)
    if locked.status != GroupInvitationStatus.PENDING:
        raise ValidationError("Seule une invitation en attente peut être rattachée.")
    if locked.email and normalize_email(profile.email) != normalize_email(locked.email):
        raise ValidationError("Le Profil ne correspond pas à l'e-mail de l'invitation.")
    if locked.phone and normalize_phone(profile.phone or "") != normalize_phone(locked.phone):
        raise ValidationError("Le Profil ne correspond pas au téléphone de l'invitation.")
    locked.profile = profile
    locked.identity_verified_at = timezone.now()
    locked.verification_digest = ""
    locked.verification_expires_at = None
    locked.save(
        update_fields=[
            "profile",
            "identity_verified_at",
            "verification_digest",
            "verification_expires_at",
            "updated_at",
        ]
    )
    return locked


def _invitation_matches_profile(invitation: GroupInvitation, profile) -> bool:
    if invitation.profile_id:
        return invitation.profile_id == profile.pk
    if invitation.email:
        return bool(
            getattr(profile, "email_verified", False)
            and normalize_email(invitation.email) == normalize_email(profile.email)
        )
    if invitation.phone:
        return bool(
            getattr(profile, "phone_verified", False)
            and normalize_phone(invitation.phone) == normalize_phone(profile.phone or "")
        )
    # Une référence externe seule n'est jamais une preuve self-service.
    return False


@transaction.atomic
def request_invitation_email_verification(*, profile, token: str) -> GroupInvitation:
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous avant de vérifier cette invitation.")
    digest = _token_digest(token)
    pointer = GroupInvitation.objects.filter(token_digest=digest).values("group_id").first()
    if not pointer:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    locked_group = _lock_group(pointer["group_id"])
    invitation = GroupInvitation.objects.select_for_update().filter(
        token_digest=digest,
        group=locked_group,
        status=GroupInvitationStatus.PENDING,
    ).order_by().first()
    if not invitation or invitation.expires_at <= timezone.now():
        raise ValidationError("Cette invitation est invalide ou expirée.")
    if invitation.profile_id:
        if invitation.profile_id != profile.pk:
            raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")
        return invitation
    if not invitation.email or normalize_email(invitation.email) != normalize_email(profile.email):
        raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")

    code = f"{secrets.randbelow(100_000_000):08d}"
    invitation.verification_digest = _verification_digest(invitation.pk, code)
    invitation.verification_expires_at = timezone.now() + INVITATION_VERIFICATION_TTL
    invitation.save(
        update_fields=["verification_digest", "verification_expires_at", "updated_at"]
    )
    transaction.on_commit(
        lambda invitation_id=invitation.pk, verification_code=code: _send_invitation_verification_email(
            invitation_id,
            verification_code,
        )
    )
    return invitation


@transaction.atomic
def verify_invitation_email_identity(*, profile, token: str, code: str) -> GroupInvitation:
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous avant de vérifier cette invitation.")
    digest = _token_digest(token)
    pointer = GroupInvitation.objects.filter(token_digest=digest).values("group_id").first()
    if not pointer:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    locked_group = _lock_group(pointer["group_id"])
    invitation = GroupInvitation.objects.select_for_update().filter(
        token_digest=digest,
        group=locked_group,
        status=GroupInvitationStatus.PENDING,
    ).order_by().first()
    if not invitation or invitation.expires_at <= timezone.now():
        raise ValidationError("Cette invitation est invalide ou expirée.")
    if invitation.profile_id and invitation.profile_id != profile.pk:
        raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")
    if not invitation.email or normalize_email(invitation.email) != normalize_email(profile.email):
        raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")
    if not invitation.verification_digest or not invitation.verification_expires_at:
        raise ValidationError("Demandez d'abord un nouveau code de vérification.")
    if invitation.verification_expires_at <= timezone.now():
        raise ValidationError("Le code de vérification a expiré.")
    candidate = _verification_digest(invitation.pk, (code or "").strip())
    if not hmac.compare_digest(candidate, invitation.verification_digest):
        raise ValidationError("Le code de vérification est incorrect.")

    now = timezone.now()
    invitation.profile = profile
    invitation.identity_verified_at = now
    invitation.verification_digest = ""
    invitation.verification_expires_at = None
    invitation.save(
        update_fields=[
            "profile",
            "identity_verified_at",
            "verification_digest",
            "verification_expires_at",
            "updated_at",
        ]
    )
    if not getattr(profile, "email_verified", False):
        profile.email_verified = True
        profile.save(update_fields=["email_verified", "updated_at"])
    return invitation


@transaction.atomic
def accept_invitation(*, profile, token: str) -> tuple[GroupInvitation, GroupMembership]:
    if not getattr(profile, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous avant d'accepter cette invitation.")
    digest = _token_digest(token)
    pointer = GroupInvitation.objects.filter(token_digest=digest).values("group_id").first()
    if not pointer:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    locked_group = _lock_group(pointer["group_id"])
    invitation = GroupInvitation.objects.select_for_update().filter(
        token_digest=digest,
        group=locked_group,
    ).order_by().first()
    if not invitation or invitation.status != GroupInvitationStatus.PENDING:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    if invitation.expires_at <= timezone.now():
        raise ValidationError("Cette invitation a expiré.")
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Ce Groupe est archivé.")
    if not _invitation_matches_profile(invitation, profile):
        raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté ou son identité n'est pas encore vérifiée.")

    membership = GroupMembership.objects.select_for_update().filter(
        group=locked_group,
        profile=profile,
    ).order_by().first()
    now = timezone.now()
    if membership and membership.status in {
        GroupMembershipStatus.SUSPENDED,
        GroupMembershipStatus.REMOVED,
    }:
        raise ValidationError("Cette appartenance ne peut pas être réactivée par un lien d'invitation.")
    if membership:
        membership.status = GroupMembershipStatus.ACTIVE
        membership.source = GroupMembershipSource.INVITATION
        membership.joined_at = now
        membership.verified_at = now
        if invitation.external_reference:
            membership.external_reference = invitation.external_reference
        membership.save()
    else:
        membership = GroupMembership.objects.create(
            group=locked_group,
            profile=profile,
            status=GroupMembershipStatus.ACTIVE,
            source=GroupMembershipSource.INVITATION,
            joined_at=now,
            verified_at=now,
            external_reference=invitation.external_reference,
        )

    invitation.status = GroupInvitationStatus.ACCEPTED
    invitation.profile = profile
    invitation.identity_verified_at = invitation.identity_verified_at or now
    invitation.accepted_at = now
    invitation.token_digest = _new_invitation_token()[1]
    invitation.verification_digest = ""
    invitation.verification_expires_at = None
    invitation.save(
        update_fields=[
            "status",
            "profile",
            "identity_verified_at",
            "accepted_at",
            "token_digest",
            "verification_digest",
            "verification_expires_at",
            "updated_at",
        ]
    )
    return invitation, membership


@transaction.atomic
def reject_invitation(*, profile, token: str) -> GroupInvitation:
    digest = _token_digest(token)
    pointer = GroupInvitation.objects.filter(token_digest=digest).values("group_id").first()
    if not pointer:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    locked_group = _lock_group(pointer["group_id"])
    invitation = GroupInvitation.objects.select_for_update().filter(
        token_digest=digest,
        group=locked_group,
        status=GroupInvitationStatus.PENDING,
    ).order_by().first()
    if not invitation:
        raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
    if not _invitation_matches_profile(invitation, profile):
        raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")
    invitation.status = GroupInvitationStatus.REJECTED
    invitation.rejected_at = timezone.now()
    invitation.token_digest = _new_invitation_token()[1]
    invitation.verification_digest = ""
    invitation.verification_expires_at = None
    invitation.save(
        update_fields=[
            "status",
            "rejected_at",
            "token_digest",
            "verification_digest",
            "verification_expires_at",
            "updated_at",
        ]
    )
    return invitation


@transaction.atomic
def revoke_invitation(*, actor, invitation) -> GroupInvitation:
    locked_group = _lock_group(invitation.group_id)
    require_group_permission(actor, PermissionCode.GROUP_INVITATIONS_MANAGE, locked_group)
    locked = GroupInvitation.objects.select_for_update().order_by().get(pk=invitation.pk)
    if locked.status == GroupInvitationStatus.REVOKED:
        return locked
    if locked.status != GroupInvitationStatus.PENDING:
        raise ValidationError("Cette invitation n'est plus révocable.")
    locked.status = GroupInvitationStatus.REVOKED
    locked.token_digest = _new_invitation_token()[1]
    locked.verification_digest = ""
    locked.verification_expires_at = None
    locked.save(
        update_fields=[
            "status",
            "token_digest",
            "verification_digest",
            "verification_expires_at",
            "updated_at",
        ]
    )
    return locked


@transaction.atomic
def create_snapshot(*, actor, group, name: str = "") -> GroupSnapshot:
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_SNAPSHOTS_CREATE, locked_group)
    memberships = list(
        GroupMembership.objects.select_for_update()
        .filter(group=locked_group, status=GroupMembershipStatus.ACTIVE)
        .order_by()
        .only("profile_id", "external_reference", "joined_at")
    )
    label = (name or "").strip() or f"Snapshot du {timezone.localtime():%d/%m/%Y %H:%M}"
    snapshot = GroupSnapshot.objects.create(
        group=locked_group,
        name=label,
        created_by=actor,
        member_count=0,
    )
    GroupSnapshotMember.objects.bulk_create(
        [
            GroupSnapshotMember(
                snapshot=snapshot,
                profile_id=membership.profile_id,
                external_reference=membership.external_reference,
                joined_at=membership.joined_at,
            )
            for membership in memberships
        ]
    )
    GroupSnapshot.objects.filter(pk=snapshot.pk).update(member_count=len(memberships))
    snapshot.member_count = len(memberships)
    return snapshot


@transaction.atomic
def transfer_personal_group_ownership(*, actor, group, new_owner) -> Group:
    locked_group = _lock_group(group)
    if not locked_group.owner_profile_id:
        raise ValidationError("Un Groupe appartenant à un Espace ne se transfère pas à un Profil.")
    require_group_permission(actor, PermissionCode.GROUP_OWNERSHIP_MANAGE, locked_group)
    if locked_group.owner_profile_id == new_owner.pk:
        return locked_group
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Archivez ou réactivez le Groupe avant un transfert de propriété.")

    old_owner_id = locked_group.owner_profile_id
    owner_role = get_system_role(SystemRoleCode.GROUP_OWNER, scope_type=AuthorityScope.GROUP)
    grant_group_role(
        profile=new_owner,
        group=locked_group,
        role=owner_role,
        granted_by=actor,
        source="ownership-transfer",
    )
    locked_group.owner_profile = new_owner
    locked_group.save(update_fields=["owner_profile", "updated_at"])
    old_mandates = list(
        Mandate.objects.select_for_update()
        .filter(
            profile_id=old_owner_id,
            group=locked_group,
            scope_type=AuthorityScope.GROUP,
            role_id=owner_role.pk,
            status=MandateStatus.ACTIVE,
        )
        .order_by()
    )
    for mandate in old_mandates:
        revoke_mandate(mandate=mandate, actor=actor)
    return locked_group


@transaction.atomic
def assign_group_responsibility(*, actor, group, profile, role_code: str):
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_OWNERSHIP_MANAGE, locked_group)
    if role_code not in {SystemRoleCode.GROUP_ADMIN, SystemRoleCode.GROUP_MODERATOR}:
        raise ValidationError("Seuls les rôles administrateur ou modérateur peuvent être délégués ici.")
    return replace_standard_group_role(
        profile=profile,
        group=locked_group,
        role_code=role_code,
        granted_by=actor,
        source="group-delegation",
    )


@dataclass(frozen=True)
class ParsedImportRow:
    line: int
    email: str = ""
    phone: str = ""
    external_reference: str = ""
    first_name: str = ""
    last_name: str = ""


@dataclass
class GroupImportResult:
    members_added: int = 0
    invitations_created: int = 0
    duplicates_ignored: int = 0
    invalid_lines: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_issues(self):
        return self.invalid_lines + self.conflicts


def parse_group_csv(upload) -> tuple[list[ParsedImportRow], GroupImportResult]:
    raw = upload.read() if hasattr(upload, "read") else upload
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("Le fichier CSV doit être encodé en UTF-8.") from exc
    else:
        text = str(raw or "")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("Le fichier CSV doit contenir une ligne d'en-tête.")
    normalized_headers = {str(name or "").strip().lower() for name in reader.fieldnames}
    supported = {"email", "phone", "external_reference", "first_name", "last_name"}
    if not normalized_headers & {"email", "phone", "external_reference"}:
        raise ValidationError("Le CSV doit contenir au moins email, phone ou external_reference.")
    unknown = normalized_headers - supported
    if unknown:
        raise ValidationError(f"Colonnes non prises en charge : {', '.join(sorted(unknown))}.")

    rows: list[ParsedImportRow] = []
    result = GroupImportResult()
    identities: dict[tuple[str, str], ParsedImportRow] = {}
    for index, source in enumerate(reader, start=2):
        if index - 1 > IMPORT_MAX_ROWS:
            raise ValidationError(f"Un import est limité à {IMPORT_MAX_ROWS} lignes.")
        row = {str(key or "").strip().lower(): (value or "").strip() for key, value in source.items()}
        parsed = ParsedImportRow(
            line=index,
            email=normalize_email(row.get("email", "")),
            phone=normalize_phone(row.get("phone", "")),
            external_reference=row.get("external_reference", "").strip(),
            first_name=row.get("first_name", "").strip(),
            last_name=row.get("last_name", "").strip(),
        )
        if not any((parsed.email, parsed.phone, parsed.external_reference)):
            result.invalid_lines += 1
            result.errors.append(f"Ligne {index}: aucune identité exploitable.")
            continue

        keys = []
        if parsed.email:
            keys.append(("email", parsed.email))
        if parsed.phone:
            keys.append(("phone", parsed.phone))
        if parsed.external_reference:
            keys.append(("external_reference", parsed.external_reference.casefold()))
        previous = next((identities[key] for key in keys if key in identities), None)
        if previous:
            if (
                previous.email == parsed.email
                and previous.phone == parsed.phone
                and previous.external_reference == parsed.external_reference
            ):
                result.duplicates_ignored += 1
            else:
                result.conflicts += 1
                result.errors.append(f"Ligne {index}: identité contradictoire avec la ligne {previous.line}.")
            continue
        for key in keys:
            identities[key] = parsed
        rows.append(parsed)
    return rows, result


@transaction.atomic
def import_group_csv(*, actor, group, upload) -> GroupImportResult:
    # Parsing and intra-file conflict detection happen before the first write.
    rows, result = parse_group_csv(upload)
    locked_group = _lock_group(group)
    require_group_permission(actor, PermissionCode.GROUP_MEMBERS_MANAGE, locked_group)
    require_group_permission(actor, PermissionCode.GROUP_INVITATIONS_MANAGE, locked_group)
    if locked_group.status != GroupStatus.ACTIVE:
        raise ValidationError("Un Groupe archivé ne peut pas être importé.")

    for row in rows:
        try:
            profile = _resolve_profile_for_identity(email=row.email, phone=row.phone)
        except ValidationError as exc:
            result.conflicts += 1
            result.errors.append(f"Ligne {row.line}: {' '.join(exc.messages)}")
            continue

        if row.external_reference:
            ref_membership = GroupMembership.objects.filter(
                group=locked_group,
                external_reference=row.external_reference,
            ).select_related("profile").first()
            if ref_membership and (profile is None or ref_membership.profile_id != profile.pk):
                result.conflicts += 1
                result.errors.append(
                    f"Ligne {row.line}: la référence externe appartient déjà à un autre membre."
                )
                continue

        if profile:
            membership = GroupMembership.objects.filter(group=locked_group, profile=profile).first()
            if membership:
                if membership.status == GroupMembershipStatus.ACTIVE:
                    if row.external_reference and not membership.external_reference:
                        try:
                            with transaction.atomic():
                                membership.external_reference = row.external_reference
                                membership.save(update_fields=["external_reference", "updated_at"])
                        except IntegrityError:
                            result.conflicts += 1
                            result.errors.append(f"Ligne {row.line}: référence externe déjà utilisée.")
                            continue
                    result.duplicates_ignored += 1
                else:
                    result.conflicts += 1
                    result.errors.append(
                        f"Ligne {row.line}: un historique d'appartenance non actif existe; aucune réactivation automatique."
                    )
                continue
            try:
                with transaction.atomic():
                    GroupMembership.objects.create(
                        group=locked_group,
                        profile=profile,
                        status=GroupMembershipStatus.ACTIVE,
                        source=GroupMembershipSource.IMPORT,
                        verified_at=timezone.now(),
                        external_reference=row.external_reference,
                    )
                result.members_added += 1
            except IntegrityError:
                result.conflicts += 1
                result.errors.append(f"Ligne {row.line}: conflit d'unicité sur l'appartenance.")
            continue

        pending = GroupInvitation.objects.filter(
            group=locked_group,
            status=GroupInvitationStatus.PENDING,
        )
        if row.email:
            pending = pending.filter(email__iexact=row.email)
        elif row.phone:
            pending = pending.filter(phone=row.phone)
        else:
            pending = pending.filter(external_reference=row.external_reference)
        if pending.exists():
            result.duplicates_ignored += 1
            continue
        try:
            with transaction.atomic():
                _create_or_refresh_invitation_locked(
                    group=locked_group,
                    invited_by=actor,
                    email=row.email,
                    phone=row.phone,
                    external_reference=row.external_reference,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    send_email=bool(row.email),
                )
            result.invitations_created += 1
        except (IntegrityError, ValidationError) as exc:
            result.conflicts += 1
            if isinstance(exc, ValidationError):
                message = " ".join(exc.messages)
            else:
                message = "conflit d'unicité pendant la création de l'invitation"
            result.errors.append(f"Ligne {row.line}: {message}.")
    return result

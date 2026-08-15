from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import GroupMembershipStatus

from .canonical_models import Audience, AudienceMember, AudienceMemberSource, AudienceStatus


def _require_manage(actor, organization):
    if not actor or not actor.is_authenticated or not can(actor, PermissionCode.CRM_MANAGE, organization):
        raise PermissionDenied("Vous n’avez pas le droit de gérer les Audiences de cet Espace.")


def _validate_group_space(group, organization):
    if group.owner_profile_id:
        raise ValidationError("Un Groupe personnel ne peut pas être utilisé comme Audience d’un Espace.")
    if group.space_id != organization.pk:
        raise ValidationError("Le Groupe doit appartenir au même Espace que l’Audience.")


def _validate_snapshot_space(snapshot, organization):
    _validate_group_space(snapshot.group, organization)


@transaction.atomic
def create_static_audience(*, organization, name, created_by, description="", profiles=()):
    _require_manage(created_by, organization)
    audience = Audience(
        organization=organization,
        name=(name or "").strip(),
        description=(description or "").strip(),
        created_by=created_by,
    )
    audience.full_clean()
    audience.save()
    for profile in profiles:
        add_audience_member(audience=audience, profile=profile, actor=created_by)
    return audience


@transaction.atomic
def add_audience_member(*, audience, profile, actor, source=AudienceMemberSource.MANUAL, source_group=None, source_snapshot=None):
    _require_manage(actor, audience.organization)
    if audience.status != AudienceStatus.ACTIVE:
        raise ValidationError("Une Audience archivée ne peut plus recevoir de membres.")
    existing = AudienceMember.objects.filter(audience=audience, profile=profile).first()
    if existing:
        return existing
    member = AudienceMember(
        audience=audience,
        profile=profile,
        source=source,
        source_group=source_group,
        source_snapshot=source_snapshot,
    )
    member.full_clean()
    member.save()
    return member


@transaction.atomic
def create_audience_from_group(*, organization, group, name, created_by, description=""):
    _require_manage(created_by, organization)
    _validate_group_space(group, organization)
    audience = Audience(
        organization=organization,
        name=(name or "").strip(),
        description=(description or "").strip(),
        source_group=group,
        created_by=created_by,
    )
    audience.full_clean()
    audience.save()
    profile_ids = group.memberships.filter(status=GroupMembershipStatus.ACTIVE).values_list("profile_id", flat=True)
    AudienceMember.objects.bulk_create(
        [
            AudienceMember(
                audience=audience,
                profile_id=profile_id,
                source=AudienceMemberSource.GROUP,
                source_group=group,
            )
            for profile_id in profile_ids
        ],
        ignore_conflicts=True,
    )
    return audience


@transaction.atomic
def create_audience_from_snapshot(*, organization, snapshot, name, created_by, description=""):
    _require_manage(created_by, organization)
    _validate_snapshot_space(snapshot, organization)
    audience = Audience(
        organization=organization,
        name=(name or "").strip(),
        description=(description or "").strip(),
        source_group=snapshot.group,
        source_snapshot=snapshot,
        created_by=created_by,
    )
    audience.full_clean()
    audience.save()
    AudienceMember.objects.bulk_create(
        [
            AudienceMember(
                audience=audience,
                profile_id=record.profile_id,
                source=AudienceMemberSource.GROUP_SNAPSHOT,
                source_group=snapshot.group,
                source_snapshot=snapshot,
            )
            for record in snapshot.members.all()
        ],
        ignore_conflicts=True,
    )
    return audience


@transaction.atomic
def archive_audience(*, audience, actor):
    _require_manage(actor, audience.organization)
    audience.status = AudienceStatus.ARCHIVED
    audience.save(update_fields=["status", "updated_at"])
    return audience

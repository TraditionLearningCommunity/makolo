from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission

from .models import Access, AccessCredential, AccessStatus, CredentialStatus


def accesses_for_profile(profile):
    if not getattr(profile, "is_authenticated", False):
        return Access.objects.none()
    return Access.objects.filter(beneficiary=profile).select_related(
        "activity", "activity__space", "occurrence", "journey", "issued_by"
    )


def valid_accesses(profile=None, *, at=None):
    at = at or timezone.now()
    queryset = Access.objects.filter(status=AccessStatus.VALID).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=at),
        Q(valid_until__isnull=True) | Q(valid_until__gt=at),
    ).select_related("activity", "activity__space", "occurrence", "journey", "beneficiary", "issued_by")
    if profile is not None:
        if not getattr(profile, "is_authenticated", False):
            return queryset.none()
        queryset = queryset.filter(beneficiary=profile)
    return queryset


def accesses_for_activity_manager(profile, *, activity=None, occurrence=None):
    queryset = Access.objects.select_related(
        "activity", "activity__space", "occurrence", "journey", "beneficiary", "issued_by"
    )
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_ACCESS_VIEW)
    if allowed is not None:
        queryset = queryset.filter(activity_id__in=allowed)
    if activity is not None:
        queryset = queryset.filter(activity=activity)
    if occurrence is not None:
        queryset = queryset.filter(occurrence=occurrence)
    return queryset


def resolve_credential(*, public_id, version=None):
    queryset = AccessCredential.objects.select_related("access", "access__activity", "access__occurrence")
    queryset = queryset.filter(public_id=public_id)
    if version is not None:
        queryset = queryset.filter(version=version)
    return queryset.order_by("-version").first()


def active_credential_for_access(access):
    return AccessCredential.objects.filter(access=access, status=CredentialStatus.ACTIVE).order_by("-version").first()


def access_from_ticket(ticket):
    if not getattr(ticket, "access_id", None):
        return None
    return Access.objects.select_related(
        "activity", "activity__space", "occurrence", "journey", "beneficiary", "issued_by"
    ).filter(pk=ticket.access_id).first()

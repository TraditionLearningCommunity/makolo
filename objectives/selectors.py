from django.db.models import Count, Q

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from journeys.models import Journey

from .models import Dossier, DossierJourneyLink


def dossiers_for_profile(profile):
    if not getattr(profile, "is_authenticated", False):
        return Dossier.objects.none()
    view_spaces = space_ids_with_permission(profile, PermissionCode.SPACE_VIEW)
    manage_spaces = space_ids_with_permission(profile, PermissionCode.SPACE_MANAGE)
    queryset = Dossier.objects.select_related("owner_profile", "owning_space", "created_by")
    if view_spaces is None or manage_spaces is None:
        visible = queryset
    else:
        space_ids = set(view_spaces) | set(manage_spaces)
        visible = queryset.filter(Q(owner_profile=profile) | Q(owning_space_id__in=space_ids))
    return visible.annotate(
        active_journey_count=Count("journey_links", filter=Q(journey_links__is_active=True), distinct=True)
    ).distinct()


def dossier_for_profile(profile, dossier_id):
    return dossiers_for_profile(profile).get(pk=dossier_id)


def journey_is_visible_to_profile(profile, journey):
    if not getattr(profile, "is_authenticated", False):
        return False
    if journey.beneficiary_id == profile.pk or journey.initiated_by_id == profile.pk:
        return True
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    return allowed is None or journey.activity_id in allowed


def visible_linked_journeys(profile, dossier):
    if not getattr(profile, "is_authenticated", False):
        return DossierJourneyLink.objects.none()
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    visibility = Q(journey__beneficiary=profile) | Q(journey__initiated_by=profile)
    if allowed is None:
        visibility = Q()
    elif allowed:
        visibility |= Q(journey__activity_id__in=allowed)
    return (
        DossierJourneyLink.objects.filter(dossier=dossier, is_active=True)
        .filter(visibility)
        .select_related(
            "journey",
            "journey__activity",
            "journey__occurrence",
            "journey__beneficiary",
            "journey__external_beneficiary",
            "linked_by",
        )
        .order_by("linked_at", "id")
    )


def linkable_journeys_for_profile(profile, dossier=None):
    if not getattr(profile, "is_authenticated", False):
        return Journey.objects.none()
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    visibility = Q(beneficiary=profile) | Q(initiated_by=profile)
    if allowed is None:
        queryset = Journey.objects.all()
    else:
        if allowed:
            visibility |= Q(activity_id__in=allowed)
        queryset = Journey.objects.filter(visibility)
    if dossier is not None:
        queryset = queryset.exclude(dossier_links__dossier=dossier, dossier_links__is_active=True)
    return queryset.select_related("activity", "occurrence", "beneficiary", "external_beneficiary", "initiated_by").distinct()

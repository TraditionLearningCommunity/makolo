from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from authorization.services import activity_ids_with_permission, dossier_ids_with_permission, space_ids_with_permission
from journeys.models import Journey
from organizations.models import TeamMembershipStatus

from .models import Dossier, DossierAssignment, DossierAssignmentStatus, DossierJourneyDependency, DossierJourneyDependencyState, DossierJourneyLink


User = get_user_model()


def dossiers_for_profile(profile):
    if not getattr(profile, "is_authenticated", False): return Dossier.objects.none()
    view_spaces = space_ids_with_permission(profile, PermissionCode.SPACE_VIEW)
    manage_spaces = space_ids_with_permission(profile, PermissionCode.SPACE_MANAGE)
    dossier_permissions = [dossier_ids_with_permission(profile, PermissionCode.DOSSIER_VIEW), dossier_ids_with_permission(profile, PermissionCode.DOSSIER_MANAGE), dossier_ids_with_permission(profile, PermissionCode.DOSSIER_AUTHORITY_MANAGE)]
    queryset = Dossier.objects.select_related("owner_profile", "owning_space", "created_by")
    if view_spaces is None or manage_spaces is None or any(ids is None for ids in dossier_permissions): visible = queryset
    else:
        space_ids = set(view_spaces) | set(manage_spaces); dossier_ids = set().union(*(set(ids) for ids in dossier_permissions))
        visible = queryset.filter(Q(owner_profile=profile) | Q(owning_space_id__in=space_ids) | Q(pk__in=dossier_ids))
    return visible.annotate(active_journey_count=Count("journey_links", filter=Q(journey_links__is_active=True), distinct=True)).distinct()


def dossier_for_profile(profile, dossier_id): return dossiers_for_profile(profile).get(pk=dossier_id)


def journey_is_visible_to_profile(profile, journey):
    if not getattr(profile, "is_authenticated", False): return False
    if journey.beneficiary_id == profile.pk or journey.initiated_by_id == profile.pk: return True
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    return allowed is None or journey.activity_id in allowed


def _visible_link_filter(profile):
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    visibility = Q(journey__beneficiary=profile) | Q(journey__initiated_by=profile)
    if allowed is None: return Q()
    if allowed: visibility |= Q(journey__activity_id__in=allowed)
    return visibility


def visible_linked_journeys(profile, dossier):
    if not getattr(profile, "is_authenticated", False): return DossierJourneyLink.objects.none()
    return DossierJourneyLink.objects.filter(dossier=dossier, is_active=True).filter(_visible_link_filter(profile)).select_related("journey", "journey__activity", "journey__occurrence", "journey__beneficiary", "journey__external_beneficiary", "linked_by").order_by("linked_at", "id")


def linkable_journeys_for_profile(profile, dossier=None):
    if not getattr(profile, "is_authenticated", False): return Journey.objects.none()
    allowed = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_REQUESTS_VIEW); visibility = Q(beneficiary=profile) | Q(initiated_by=profile)
    if allowed is None: queryset = Journey.objects.all()
    else:
        if allowed: visibility |= Q(activity_id__in=allowed)
        queryset = Journey.objects.filter(visibility)
    if dossier is not None: queryset = queryset.exclude(dossier_links__dossier=dossier, dossier_links__is_active=True)
    return queryset.select_related("activity", "occurrence", "beneficiary", "external_beneficiary", "initiated_by").distinct()


def active_dependencies_for_dossier(dossier):
    return DossierJourneyDependency.objects.filter(dossier=dossier, state=DossierJourneyDependencyState.ACTIVE).select_related("dependent_link__journey__activity", "required_link__journey__activity").order_by("created_at", "id")


def visible_dependencies_for_profile(profile, dossier):
    if not getattr(profile, "is_authenticated", False): return DossierJourneyDependency.objects.none()
    visible_link_ids = visible_linked_journeys(profile, dossier).values_list("pk", flat=True)
    return DossierJourneyDependency.objects.filter(dossier=dossier, state__in=[DossierJourneyDependencyState.ACTIVE, DossierJourneyDependencyState.WAIVED], dependent_link_id__in=visible_link_ids, required_link_id__in=visible_link_ids).select_related("dependent_link__journey__activity", "required_link__journey__activity").order_by("created_at", "id")


def dependency_candidates_for_profile(profile, dossier): return visible_linked_journeys(profile, dossier)


def active_assignments_for_dossier(dossier):
    return DossierAssignment.objects.filter(dossier=dossier, status=DossierAssignmentStatus.ACTIVE).select_related("assignee", "assigned_by").order_by("assigned_at", "id")


def assignment_for_profile(dossier, profile): return active_assignments_for_dossier(dossier).filter(assignee=profile).first()


def current_dossier_authority_mandates(dossier, *, at=None):
    return current_mandates(at=at).filter(scope_type=AuthorityScope.DOSSIER, dossier=dossier).select_related("profile", "role").order_by("profile__first_name", "profile__last_name", "role__name")


def collaboration_candidates_for_dossier(dossier):
    """Bounded existing principals only; this is not a global user search."""
    if dossier.owning_space_id:
        return User.objects.filter(is_active=True, team_memberships__team__organization=dossier.owning_space, team_memberships__status=TeamMembershipStatus.ACTIVE).distinct().order_by("first_name", "last_name", "username", "pk")
    known_ids = {dossier.owner_profile_id}; known_ids.update(current_dossier_authority_mandates(dossier).values_list("profile_id", flat=True)); known_ids.update(active_assignments_for_dossier(dossier).values_list("assignee_id", flat=True))
    return User.objects.filter(pk__in=known_ids, is_active=True).order_by("first_name", "last_name", "username", "pk")

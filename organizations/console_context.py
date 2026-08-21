from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import activity_ids_with_permission, effective_permission_codes, has_platform_authority
from scanner.models import ScannerAssignment

from .models import Organization


SPACE_NAVIGATION = (
    ("Activité", (("activities", "Activités", "calendar-days"), ("requests", "Demandes", "calendar-search"), ("access", "Accès", "badge-check"))),
    ("Transport", (("transport", "Routes · Départs · Véhicules", "bus-front"),)),
    ("Commercial", (("offers", "Tarifs", "ticket"), ("orders", "Commandes", "layout-dashboard"), ("payments", "Paiements", "wallet-cards"), ("promotions", "Promotions", "badge-percent"))),
    ("Publics", (("groups", "Groupes", "users-round"), ("crm", "Contacts", "contact-round"), ("audiences", "Audiences", "users-round"))),
    ("Exploitation", (("places", "Lieux", "building-2"), ("control", "Contrôle d’accès", "scan-line"), ("operations", "Opérations", "shield-check"))),
    ("Pilotage", (("analytics", "Analyses", "chart-spline"), ("automation", "Automatisations", "sparkles"))),
    ("Espace", (("team", "Équipe", "users-round"), ("settings", "Paramètres", "building-2"))),
)


def _current_mandates(profile):
    now = timezone.now()
    if not getattr(profile, "is_authenticated", False):
        return Mandate.objects.none()
    return (
        Mandate.objects.filter(profile=profile, status=MandateStatus.ACTIVE, revoked_at__isnull=True, role__is_active=True)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .select_related("role", "space", "activity", "activity__space")
    )


def authorized_space_ids(profile):
    if not getattr(profile, "is_authenticated", False):
        return set()
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile):
        return None
    mandates = _current_mandates(profile)
    ids = set(mandates.filter(scope_type=AuthorityScope.SPACE).exclude(space_id=None).values_list("space_id", flat=True))
    ids.update(mandates.filter(scope_type=AuthorityScope.ACTIVITY).exclude(activity__space_id=None).values_list("activity__space_id", flat=True))
    now = timezone.now()
    ids.update(
        ScannerAssignment.objects.filter(agent=profile, is_active=True)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .exclude(activity__space_id=None)
        .values_list("activity__space_id", flat=True)
    )
    return ids


def authorized_spaces(profile):
    ids = authorized_space_ids(profile)
    queryset = Organization.objects.order_by("name")
    return queryset if ids is None else queryset.filter(pk__in=ids)


def has_space_authority(profile, space):
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile):
        return True
    return _current_mandates(profile).filter(scope_type=AuthorityScope.SPACE, space=space).exists()


def activity_ids_for_space(profile, space):
    if not getattr(profile, "is_authenticated", False):
        return set()
    if getattr(profile, "is_superuser", False) or has_platform_authority(profile) or has_space_authority(profile, space):
        return None
    mandates = _current_mandates(profile).filter(scope_type=AuthorityScope.ACTIVITY, activity__space=space)
    ids = set(mandates.values_list("activity_id", flat=True))
    now = timezone.now()
    ids.update(
        ScannerAssignment.objects.filter(agent=profile, is_active=True, activity__space=space)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .values_list("activity_id", flat=True)
    )
    return ids


def _space_role_codes(profile, space):
    return set(
        _current_mandates(profile)
        .filter(scope_type=AuthorityScope.SPACE, space=space)
        .values_list("role__code", flat=True)
    )


def _has_space_permission_outside_activity_manager(profile, space, permission_code):
    return (
        _current_mandates(profile)
        .filter(
            scope_type=AuthorityScope.SPACE,
            space=space,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        )
        .exclude(role__code=SystemRoleCode.ACTIVITY_MANAGER)
        .exists()
    )


def _has_activity_capability(profile, space, permission_code):
    permitted = activity_ids_with_permission(profile, permission_code)
    if permitted is None:
        return True
    if not permitted:
        return False
    from activities.models import Activity
    return Activity.objects.filter(space=space, pk__in=permitted).exists()


def _module_allowed(profile, space, key, *, space_permissions, limited, space_role_codes):
    if key in {"activities", "transport"}:
        return PermissionCode.SPACE_ACTIVITIES_VIEW in space_permissions or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_VIEW)
    if key == "requests":
        return _has_activity_capability(profile, space, PermissionCode.ACTIVITY_REQUESTS_VIEW)
    if key == "access":
        return bool({PermissionCode.TICKETS_VIEW, PermissionCode.ACCESS_MANAGE} & space_permissions) or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_ACCESS_VIEW)
    if key == "offers":
        return _has_activity_capability(profile, space, PermissionCode.ACTIVITY_COMMERCE_VIEW) or PermissionCode.SPACE_ACTIVITIES_VIEW in space_permissions
    if key == "orders":
        return PermissionCode.ORDERS_VIEW in space_permissions or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_COMMERCE_VIEW)
    if key == "payments":
        return PermissionCode.FINANCE_VIEW in space_permissions
    if key == "promotions":
        return PermissionCode.PROMOTIONS_VIEW in space_permissions
    if key == "groups":
        return PermissionCode.SPACE_GROUPS_VIEW in space_permissions
    if key in {"crm", "audiences"}:
        if PermissionCode.CRM_VIEW not in space_permissions:
            return False
        if SystemRoleCode.ACTIVITY_MANAGER not in space_role_codes:
            return True
        return _has_space_permission_outside_activity_manager(profile, space, PermissionCode.CRM_VIEW)
    if key == "places":
        return PermissionCode.SPACE_PLACES_VIEW in space_permissions
    if key == "control":
        return PermissionCode.ACCESS_MANAGE in space_permissions or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_ACCESS_SCAN)
    if key == "operations":
        return _has_activity_capability(profile, space, PermissionCode.ACTIVITY_OPERATIONS_VIEW)
    if key == "analytics":
        return PermissionCode.ANALYTICS_VIEW in space_permissions or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_VIEW)
    if key == "automation":
        return PermissionCode.SPACE_MANAGE in space_permissions or _has_activity_capability(profile, space, PermissionCode.ACTIVITY_MANAGE)
    if key == "team":
        return not limited and PermissionCode.SPACE_TEAM_MANAGE in space_permissions
    if key == "settings":
        return not limited and PermissionCode.SPACE_MANAGE in space_permissions
    return False


@dataclass(frozen=True)
class SpaceConsoleContext:
    profile: object
    space: Organization
    space_permissions: frozenset[str]
    limited_to_activities: bool
    activity_ids: frozenset | None
    navigation_groups: tuple
    switcher_items: tuple

    @classmethod
    def build(cls, profile, space):
        allowed_ids = authorized_space_ids(profile)
        if allowed_ids is not None and space.pk not in allowed_ids:
            return None
        limited = not has_space_authority(profile, space)
        permissions = frozenset(effective_permission_codes(profile, space=space))
        role_codes = frozenset(_space_role_codes(profile, space))
        activity_ids = activity_ids_for_space(profile, space)
        if activity_ids is not None:
            activity_ids = frozenset(activity_ids)
        navigation = []
        for label, items in SPACE_NAVIGATION:
            visible = []
            for key, item_label, icon in items:
                if _module_allowed(
                    profile,
                    space,
                    key,
                    space_permissions=permissions,
                    limited=limited,
                    space_role_codes=role_codes,
                ):
                    visible.append({"key": key, "label": item_label, "icon": icon, "url": reverse(f"organizations:console-{key}", kwargs={"slug": space.slug})})
            if visible:
                navigation.append({"label": label, "items": visible})
        switcher = tuple(
            {
                "name": candidate.name,
                "slug": candidate.slug,
                "limited": not has_space_authority(profile, candidate),
                "url": reverse("organizations:console-entry", kwargs={"slug": candidate.slug}),
            }
            for candidate in authorized_spaces(profile)
        )
        return cls(profile=profile, space=space, space_permissions=permissions, limited_to_activities=limited, activity_ids=activity_ids, navigation_groups=tuple(navigation), switcher_items=switcher)

    def can(self, permission_code):
        return permission_code in self.space_permissions

    @property
    def can_manage_space(self):
        return PermissionCode.SPACE_MANAGE in self.space_permissions

    @property
    def can_manage_team(self):
        return PermissionCode.SPACE_TEAM_MANAGE in self.space_permissions

    @property
    def can_manage_activities(self):
        return PermissionCode.SPACE_ACTIVITIES_MANAGE in self.space_permissions

    @property
    def can_view_finance(self):
        return PermissionCode.FINANCE_VIEW in self.space_permissions

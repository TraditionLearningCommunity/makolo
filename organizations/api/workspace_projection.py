from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import (
    activity_ids_with_direct_permission,
    current_mandates,
    has_direct_space_permission,
)
from organizations.models import Organization, TeamMembershipStatus
from organizations.space_product import (
    operating_preset_for_space,
    operational_footprint_for_space,
)
from trust.selectors import active_public_verifications_for_space


def _space_mandates(profile, space):
    if not getattr(profile, "is_authenticated", False):
        return current_mandates().none()
    return current_mandates().filter(
        profile=profile,
        scope_type=AuthorityScope.SPACE,
        space=space,
    )


def _has_space_permission(profile, space, permission_code):
    return has_direct_space_permission(profile, space, permission_code)


def _activity_ids_with_space_context(profile, space, permission_code):
    ids = activity_ids_with_direct_permission(profile, permission_code)
    if not ids:
        return set()
    return set(
        space.activities.filter(pk__in=ids).values_list("pk", flat=True)
    )


def _has_activity_permission(profile, space, permission_code):
    return bool(_activity_ids_with_space_context(profile, space, permission_code))


def _has_activity_permission_pair(profile, space, first, second):
    first_ids = _activity_ids_with_space_context(profile, space, first)
    second_ids = _activity_ids_with_space_context(profile, space, second)
    return bool(first_ids & second_ids)


def has_direct_space_authority(profile, space):
    return _space_mandates(profile, space).exists()


def workspace_spaces(profile):
    """Return Spaces reachable from explicit Space/Activity authority.

    Platform authority and operational Assignments are deliberately excluded:
    Platform supervises through its own contract, while Assignment expresses
    responsibility and never becomes Permission/Mandate.
    """
    if not getattr(profile, "is_authenticated", False):
        return Organization.objects.none()
    mandates = current_mandates().filter(profile=profile)
    ids = set(
        mandates.filter(scope_type=AuthorityScope.SPACE)
        .exclude(space_id=None)
        .values_list("space_id", flat=True)
    )
    ids.update(
        mandates.filter(scope_type=AuthorityScope.ACTIVITY)
        .exclude(activity__space_id=None)
        .values_list("activity__space_id", flat=True)
    )
    return Organization.objects.filter(pk__in=ids).order_by("name")


def _responsibility_projection(profile, space):
    mandates = list(
        current_mandates()
        .filter(profile=profile)
        .filter(
            __import__("django.db.models", fromlist=["Q"]).Q(
                scope_type=AuthorityScope.SPACE,
                space=space,
            )
            | __import__("django.db.models", fromlist=["Q"]).Q(
                scope_type=AuthorityScope.ACTIVITY,
                activity__space=space,
            )
        )
        .select_related("role", "activity")
        .order_by("scope_type", "role__name", "activity__title", "pk")
    )
    perspectives = []
    if mandates:
        perspectives.append({
            "key": "all",
            "label": "Toutes mes responsabilités",
            "scope": "space",
            "combined": True,
        })
    for mandate in mandates:
        row = {
            "key": f"mandate:{mandate.pk}",
            "label": mandate.role.name,
            "scope": mandate.scope_type,
            "combined": False,
        }
        if mandate.scope_type == AuthorityScope.ACTIVITY:
            row["activity"] = {
                "id": str(mandate.activity_id),
                "title": mandate.activity.title,
            }
        perspectives.append(row)
    return perspectives


def _module(key, *, status="active", capabilities=(), links=None, notes=()):
    return {
        "key": key,
        "scope": "space",
        "contract_status": status,
        "capabilities": list(capabilities),
        "links": links or {},
        "notes": list(notes),
    }


def build_space_workspace(profile, space):
    if not workspace_spaces(profile).filter(pk=space.pk).exists():
        return None

    modules = []

    partner_manage = _has_space_permission(profile, space, PermissionCode.PARTNERS_MANAGE)
    partner_finance = _has_space_permission(profile, space, PermissionCode.PARTNERS_FINANCE)
    if partner_manage or partner_finance:
        caps = ["view"]
        if partner_manage:
            caps += ["manage_partners", "manage_campaigns", "manage_codes"]
        if partner_finance:
            caps += ["view_finance", "manage_payouts"]
        links = {
            "partners": f"/api/v1/partners/partners/?organization={space.pk}",
            "campaigns": f"/api/v1/partners/campaigns/?organization={space.pk}",
            "codes": f"/api/v1/partners/codes/?organization={space.pk}",
        }
        if partner_finance:
            links.update({
                "commissions": f"/api/v1/partners/commissions/?organization={space.pk}",
                "payouts": f"/api/v1/partners/payouts/?organization={space.pk}",
            })
        modules.append(_module("partners", capabilities=caps, links=links))

    growth_view = _has_space_permission(profile, space, PermissionCode.ANALYTICS_GROWTH_VIEW)
    growth_manage = _has_space_permission(profile, space, PermissionCode.MARKETING_MANAGE)
    growth_feedback = _has_space_permission(profile, space, PermissionCode.GROWTH_FEEDBACK_VIEW)
    growth_finance = _has_space_permission(profile, space, PermissionCode.ANALYTICS_FINANCIALS_VIEW)
    if growth_view or growth_manage or growth_feedback or growth_finance:
        caps, links = [], {}
        if growth_view:
            caps.append("view")
            links["summary"] = f"/api/v1/growth/organizations/{space.slug}/"
        if growth_manage:
            caps.append("manage_acquisition")
            links["links"] = f"/api/v1/growth/links/?organization={space.slug}"
        if growth_feedback:
            caps.append("view_private_feedback")
            links["feedback"] = f"/api/v1/growth/feedback/?organization={space.slug}"
        if growth_finance:
            caps.append("view_financials")
        modules.append(_module(
            "growth",
            status="active_with_event_compatibility",
            capabilities=caps,
            links=links,
            notes=("MarketingLink/EventFeedback keep Event adapters; Growth summary remains Space-owned.",),
        ))

    analytics_view = _has_space_permission(
        profile,
        space,
        PermissionCode.ANALYTICS_VIEW,
    )
    if analytics_view:
        caps = ["view"]
        links = {
            "overview": f"/api/v1/analytics/overview/?organization={space.slug}"
        }
        if growth_view:
            links["growth"] = f"/api/v1/analytics/growth/organizations/{space.slug}/"
        if growth_finance:
            caps.append("view_financials")
        modules.append(_module(
            "analytics",
            status="active_with_vertical_adapters",
            capabilities=caps,
            links=links,
            notes=("Event and Service analytics remain vertical adapters over canonical owners.",),
        ))

    loyalty_view = _has_space_permission(profile, space, PermissionCode.LOYALTY_VIEW)
    loyalty_manage = _has_space_permission(profile, space, PermissionCode.LOYALTY_MANAGE)
    loyalty_finance = _has_space_permission(profile, space, PermissionCode.LOYALTY_FINANCE)
    if loyalty_view or loyalty_manage or loyalty_finance:
        caps = ["view"]
        if loyalty_manage:
            caps.append("manage")
        if loyalty_finance:
            caps.append("finance")
        modules.append(_module(
            "loyalty",
            capabilities=caps,
            links={
                "program": f"/api/v1/loyalty/organizations/{space.slug}/",
                "programs": f"/api/v1/loyalty/programs/?organization={space.pk}",
            },
        ))

    recognition_view = _has_space_permission(profile, space, PermissionCode.SPACE_RECOGNITION_VIEW)
    recognition_spend = _has_space_permission(profile, space, PermissionCode.SPACE_RECOGNITION_SPEND)
    if recognition_view or recognition_spend:
        caps = ["view"]
        if recognition_spend:
            caps += ["spend", "respond_to_benefits"]
        modules.append(_module(
            "recognition",
            capabilities=caps,
            links={"summary": f"/api/v1/recognition/spaces/{space.pk}/"},
        ))

    trust_view = _has_space_permission(profile, space, PermissionCode.SPACE_TRUST_VIEW)
    trust_manage = _has_space_permission(profile, space, PermissionCode.SPACE_TRUST_MANAGE)
    if trust_view or trust_manage:
        caps = ["view"]
        links = {"summary": f"/api/v1/trust/spaces/{space.pk}/operator/"}
        if trust_manage:
            caps.append("request_verification")
            links["request_verification"] = f"/api/v1/trust/spaces/{space.pk}/verification-requests/"
        modules.append(_module("trust", capabilities=caps, links=links))

    funding_space_create = (
        _has_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE)
        and _has_space_permission(profile, space, PermissionCode.FINANCE_MANAGE)
    )
    funding_activity_manage = _has_activity_permission_pair(
        profile, space, PermissionCode.ACTIVITY_MANAGE, PermissionCode.ACTIVITY_FINANCE_MANAGE
    )
    if funding_space_create or funding_activity_manage:
        caps = ["view", "manage"]
        if funding_space_create:
            caps.append("create")
        modules.append(_module(
            "funding",
            capabilities=caps,
            links={"fundings": f"/api/v1/funding/?space={space.pk}"},
        ))

    scanner_manage = _has_space_permission(profile, space, PermissionCode.ACCESS_MANAGE) or _has_activity_permission(
        profile, space, PermissionCode.ACTIVITY_ACCESS_MANAGE
    )
    scanner_use = (
        scanner_manage
        or _has_activity_permission(profile, space, PermissionCode.ACTIVITY_ACCESS_SCAN)
    )
    if scanner_use:
        caps = ["scan"]
        if scanner_manage:
            caps.append("manage_assignments")
        modules.append(_module(
            "access_control",
            status="active_with_event_compatibility",
            capabilities=caps,
            links={
                "current_assignments": "/api/v1/scanner/assignments/current/",
                "assignments": f"/api/v1/scanner/assignments/?space={space.pk}",
            },
            notes=("Access remains the right; Event gates/logs are compatibility adapters.",),
        ))

    crm_view = _has_space_permission(profile, space, PermissionCode.CRM_VIEW)
    crm_manage = _has_space_permission(profile, space, PermissionCode.CRM_MANAGE)
    if crm_view or crm_manage:
        caps = ["view"] + (["manage"] if crm_manage else [])
        modules.append(_module(
            "crm",
            capabilities=caps,
            links={
                "contacts": f"/api/v1/crm/contacts/?organization={space.pk}",
                "audiences": f"/api/v1/crm/segments/?organization={space.pk}",
            },
        ))
        modules.append(_module(
            "automation",
            capabilities=caps,
            links={"workflows": f"/api/v1/automation/workflows/?organization={space.pk}"},
            notes=("Automation executes CRM workflows but CRM remains owner of contacts/consent.",),
        ))

    promo_view = _has_space_permission(profile, space, PermissionCode.PROMOTIONS_VIEW)
    promo_manage = _has_space_permission(profile, space, PermissionCode.PROMOTIONS_MANAGE)
    if promo_view or promo_manage:
        caps = ["view"] + (["manage"] if promo_manage else [])
        modules.append(_module(
            "promotions",
            capabilities=caps,
            links={"promotions": f"/api/v1/promotions/promotions/?organization={space.pk}"},
        ))

    operations_view = _has_activity_permission(profile, space, PermissionCode.ACTIVITY_OPERATIONS_VIEW)
    operations_manage = _has_activity_permission(profile, space, PermissionCode.ACTIVITY_OPERATIONS_MANAGE)
    if operations_view or operations_manage:
        caps = ["view"] + (["manage"] if operations_manage else [])
        modules.append(_module(
            "operations",
            status="activity_occurrence_scoped",
            capabilities=caps,
            notes=("Space Operations uses Activity/Occurrence endpoints; Platform Operations is separate.",),
        ))

    direct_space_authority = has_direct_space_authority(profile, space)
    preset = operating_preset_for_space(space)
    verification = [
        {
            "claim_type": claim.claim_type,
            "status": claim.status,
            "valid_until": claim.valid_until,
        }
        for claim in active_public_verifications_for_space(space)
    ]
    payload = {
        "space": {
            "id": str(space.pk),
            "slug": space.slug,
            "name": space.name,
            "description": space.description or None,
            "archetype": space.archetype,
            "lifecycle": space.lifecycle,
            "public_profile": space.public_profile,
        },
        "verification": {
            "verified": bool(verification),
            "claims": verification,
        },
        "authority": {
            "scope": "space" if direct_space_authority else "activity_limited",
            "limited_to_activities": not direct_space_authority,
        },
        "capabilities": {
            "update_space": _has_space_permission(profile, space, PermissionCode.SPACE_MANAGE),
            "manage_team": _has_space_permission(profile, space, PermissionCode.SPACE_TEAM_MANAGE),
            "manage_ownership": _has_space_permission(profile, space, PermissionCode.SPACE_OWNERSHIP_MANAGE),
        },
        "operating_preset": {
            "label": preset.label,
            "navigation_section_label": preset.navigation_section_label,
            "activities_label": preset.activities_label,
            "primary_business_label": preset.primary_business_label,
            "featured_modules": list(preset.featured_modules),
            "suggested_verticals": list(preset.suggested_verticals),
        },
        "responsibilities": _responsibility_projection(profile, space),
        "links": {
            "workspace": f"/api/v1/organizations/workspaces/{space.slug}/",
        },
        "modules": modules,
        "platform_modules_included": False,
    }
    if direct_space_authority:
        payload["operational_footprint"] = {
            "signals": list(operational_footprint_for_space(space).signals)
        }
        payload["team_summary"] = {
            "active_members": space.teams.filter(
                memberships__status=TeamMembershipStatus.ACTIVE,
                is_default=True,
            ).values("memberships__user_id").distinct().count()
        }
        payload["ownership_summary"] = {
            "owner_count": current_mandates().filter(
                scope_type=AuthorityScope.SPACE,
                space=space,
                role__is_system=True,
                role__code="space_owner",
            ).count(),
            "viewer_is_owner": _has_space_permission(
                profile, space, PermissionCode.SPACE_OWNERSHIP_MANAGE
            ),
        }
    return payload

from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, can

from organizations.console_context import SpaceConsoleContext


def _has_activity_permission(profile, space, permission_code):
    ids = activity_ids_with_permission(profile, permission_code)
    if ids is None:
        return space.activities.exists()
    return bool(ids) and space.activities.filter(pk__in=ids).exists()


def _has_activity_permission_pair(profile, space, first, second):
    first_ids = activity_ids_with_permission(profile, first)
    second_ids = activity_ids_with_permission(profile, second)
    if first_ids is None and second_ids is None:
        return space.activities.exists()
    if first_ids is None:
        return bool(second_ids) and space.activities.filter(pk__in=second_ids).exists()
    if second_ids is None:
        return bool(first_ids) and space.activities.filter(pk__in=first_ids).exists()
    shared = set(first_ids) & set(second_ids)
    return bool(shared) and space.activities.filter(pk__in=shared).exists()


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
    context = SpaceConsoleContext.build(profile, space)
    if context is None:
        return None

    modules = []

    partner_manage = can(profile, PermissionCode.PARTNERS_MANAGE, space)
    partner_finance = can(profile, PermissionCode.PARTNERS_FINANCE, space)
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

    growth_view = can(profile, PermissionCode.ANALYTICS_GROWTH_VIEW, space)
    growth_manage = can(profile, PermissionCode.MARKETING_MANAGE, space)
    growth_feedback = can(profile, PermissionCode.GROWTH_FEEDBACK_VIEW, space)
    growth_finance = can(profile, PermissionCode.ANALYTICS_FINANCIALS_VIEW, space)
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

    analytics_view = can(profile, PermissionCode.ANALYTICS_VIEW, space) or _has_activity_permission(
        profile, space, PermissionCode.ACTIVITY_VIEW
    )
    if analytics_view:
        caps = ["view"]
        links = {"overview": "/api/v1/analytics/overview/"}
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

    loyalty_view = can(profile, PermissionCode.LOYALTY_VIEW, space)
    loyalty_manage = can(profile, PermissionCode.LOYALTY_MANAGE, space)
    loyalty_finance = can(profile, PermissionCode.LOYALTY_FINANCE, space)
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

    recognition_view = can(profile, PermissionCode.SPACE_RECOGNITION_VIEW, space)
    recognition_spend = can(profile, PermissionCode.SPACE_RECOGNITION_SPEND, space)
    if recognition_view or recognition_spend:
        caps = ["view"]
        if recognition_spend:
            caps += ["spend", "respond_to_benefits"]
        modules.append(_module(
            "recognition",
            capabilities=caps,
            links={"summary": f"/api/v1/recognition/spaces/{space.pk}/"},
        ))

    trust_view = can(profile, PermissionCode.SPACE_TRUST_VIEW, space)
    trust_manage = can(profile, PermissionCode.SPACE_TRUST_MANAGE, space)
    if trust_view or trust_manage:
        caps = ["view"]
        links = {"summary": f"/api/v1/trust/spaces/{space.pk}/operator/"}
        if trust_manage:
            caps.append("request_verification")
            links["request_verification"] = f"/api/v1/trust/spaces/{space.pk}/verification-requests/"
        modules.append(_module("trust", capabilities=caps, links=links))

    funding_space_create = (
        can(profile, PermissionCode.SPACE_ACTIVITIES_MANAGE, space)
        and can(profile, PermissionCode.FINANCE_MANAGE, space)
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

    scanner_manage = can(profile, PermissionCode.ACCESS_MANAGE, space) or _has_activity_permission(
        profile, space, PermissionCode.ACTIVITY_ACCESS_MANAGE
    )
    scanner_use = scanner_manage or _has_activity_permission(profile, space, PermissionCode.ACTIVITY_ACCESS_SCAN)
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

    crm_view = can(profile, PermissionCode.CRM_VIEW, space)
    crm_manage = can(profile, PermissionCode.CRM_MANAGE, space)
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

    promo_view = can(profile, PermissionCode.PROMOTIONS_VIEW, space)
    promo_manage = can(profile, PermissionCode.PROMOTIONS_MANAGE, space)
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

    return {
        "space": {"id": str(space.pk), "slug": space.slug, "name": space.name},
        "authority": {
            "scope": "activity_limited" if context.limited_to_activities else "space",
            "limited_to_activities": context.limited_to_activities,
        },
        "modules": modules,
        "platform_modules_included": False,
    }

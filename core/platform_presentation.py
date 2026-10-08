"""Presentation projection for the internal, permission-driven Makolo Platform.

The canonical Permission/Mandate service is the only authority. This is not
a second role registry: each module is a view of existing permission codes.
"""
from authorization.constants import PLATFORM_PERMISSION_CODES, PermissionCode
from authorization.services import effective_permission_codes


SUBSCRIPTION_CODES = {
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,
}
RECOGNITION_CODES = {
    PermissionCode.PLATFORM_RECOGNITION_VIEW,
    PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE,
    PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH,
    PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE,
    PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE,
    PermissionCode.PLATFORM_RECOGNITION_AUDIT_VIEW,
}
OPPORTUNITY_CODES = {
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}


def platform_permission_codes(actor):
    """Keep is_staff out of product authority; fail closed for anonymous."""
    if not getattr(actor, "is_authenticated", False):
        return set()
    return set(effective_permission_codes(actor)) & set(PLATFORM_PERMISSION_CODES)


def platform_modules_for(actor):
    """Return only modules backed by a permission and a real operational path."""
    effective = platform_permission_codes(actor)
    modules = []
    if PermissionCode.PLATFORM_MANAGE in effective:
        modules.append({
            "key": "operations", "scope": "platform", "contract_status": "active",
            "capabilities": ["view", "manage"],
            "links": {"overview": "/api/v1/operations/overview/", "web": "/operations/"},
        })
    if PermissionCode.PLATFORM_TRUST_REVIEW in effective:
        modules.append({
            "key": "trust_review", "scope": "platform", "contract_status": "owner_web_contract",
            "capabilities": ["review"],
            "links": {"web_queue": "/trust/staff/", "web": "/platform/trust/"},
        })
    if effective & SUBSCRIPTION_CODES:
        modules.append({
            "key": "subscriptions", "scope": "platform", "contract_status": "owner_domain",
            "capabilities": sorted(effective & SUBSCRIPTION_CODES),
            "links": {"web": "/platform/subscriptions/"},
        })
    if effective & RECOGNITION_CODES:
        modules.append({
            "key": "recognition_governance", "scope": "platform", "contract_status": "owner_domain",
            "capabilities": sorted(effective & RECOGNITION_CODES),
            "links": {"web": "/platform/recognition/"},
        })
    if effective & OPPORTUNITY_CODES:
        modules.append({
            "key": "opportunity_curation", "scope": "platform", "contract_status": "owner_domain",
            "capabilities": sorted(effective & OPPORTUNITY_CODES),
            "links": {"web": "/platform/curation/"},
        })
    if PermissionCode.PLATFORM_MANAGE in effective:
        modules.append({
            "key": "interoperability", "scope": "platform", "contract_status": "active",
            "capabilities": ["view"],
            "links": {"api": "/api/v1/platform/interoperability/", "web": "/platform/interoperability/"},
        })
    return modules

from django import template

from analytics_app.subscription_metrics import build_subscription_metrics
from authorization.constants import PermissionCode
from authorization.services import can
from operations.subscription_forms import EntitlementRequirementForm


register = template.Library()


@register.simple_tag
def entitlement_requirement_form():
    return EntitlementRequirementForm()


@register.simple_tag(takes_context=True)
def subscription_operational_metrics(context):
    request = context.get("request")
    if request is None or not getattr(request.user, "is_authenticated", False):
        return None
    if not (
        can(request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW)
        or can(request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE)
    ):
        return None
    return build_subscription_metrics()

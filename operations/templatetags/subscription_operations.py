from django import template

from operations.subscription_forms import EntitlementRequirementForm


register = template.Library()


@register.simple_tag
def entitlement_requirement_form():
    return EntitlementRequirementForm()

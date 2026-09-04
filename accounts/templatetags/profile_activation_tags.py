from django import template

from accounts.profile_activation import build_profile_activation_summary


register = template.Library()


@register.simple_tag(takes_context=True)
def profile_activation_summary(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    return build_profile_activation_summary(user)

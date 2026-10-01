from django import template

from accounts.activation_views import DISCOVER_PROMPT_SESSION_KEY
from accounts.profile_activation import build_profile_activation_summary
from core.web.request_context import get_request_context
from topics.models import ProfileInterest, Topic


register = template.Library()


@register.simple_tag(takes_context=True)
def profile_activation_summary(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    request_context = get_request_context(request)
    if not request_context.surface.needs_capability("profile_activation"):
        return None
    return request_context.memoize(
        ("profile_activation", user.pk),
        lambda: build_profile_activation_summary(user),
    )


@register.inclusion_tag("accounts/_discover_interest_prompt.html", takes_context=True)
def discover_interest_prompt(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    visible = bool(
        getattr(user, "is_authenticated", False)
        and not request.session.get(DISCOVER_PROMPT_SESSION_KEY, False)
        and not ProfileInterest.objects.filter(profile=user).exists()
    )
    topics = Topic.objects.filter(is_active=True).order_by("label", "code")[:5] if visible else ()
    return {
        "request": request,
        "show_interest_prompt": visible and bool(topics),
        "interest_prompt_topics": topics,
    }

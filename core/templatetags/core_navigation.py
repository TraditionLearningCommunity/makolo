from django import template

from core.capabilities import get_web_capabilities
from core.web.request_context import request_memoize


register = template.Library()


@register.simple_tag
def web_capabilities(user):
    return get_web_capabilities(user)


from core.personal_navigation import personal_surface_owner


@register.simple_tag
def personal_navigation(request):
    return request_memoize(
        request,
        ("personal_navigation",),
        lambda: personal_surface_owner(request),
    )

from django import template

from core.capabilities import get_web_capabilities


register = template.Library()


@register.simple_tag
def web_capabilities(user):
    return get_web_capabilities(user)


from core.personal_navigation import personal_surface_owner


@register.simple_tag
def personal_navigation(request):
    return personal_surface_owner(request)

from django import template

from core.capabilities import get_web_capabilities


register = template.Library()


@register.simple_tag
def web_capabilities(user):
    return get_web_capabilities(user)

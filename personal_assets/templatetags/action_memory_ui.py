from django import template
from django.middleware.csrf import get_token

from personal_assets.action_memory import action_memory_for_journey


register = template.Library()


@register.inclusion_tag("personal_assets/_action_memory_panel.html", takes_context=True)
def action_memory_panel(context, journey):
    request = context["request"]
    return {
        "journey": journey,
        "csrf_token": get_token(request),
        "memory_candidates": action_memory_for_journey(actor=request.user, journey=journey),
    }

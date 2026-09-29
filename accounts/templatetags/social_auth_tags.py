from django import template

from accounts.social_providers import social_provider_statuses


register = template.Library()


@register.simple_tag
def makolo_social_providers():
    """Expose only selected providers that are actually usable in this environment."""
    return [
        provider
        for provider in social_provider_statuses()
        if provider["configured"]
    ]

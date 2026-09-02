from django import template

from social.personal import personal_history_extensions, personal_stats

register = template.Library()


@register.simple_tag
def m5_personal_history(profile):
    if not getattr(profile, "is_authenticated", False):
        return {"stats": None, "extensions": {}}
    return {"stats": personal_stats(profile), "extensions": personal_history_extensions(profile)}

from django import template

from preparation.services import resources_for_journey


register = template.Library()


@register.inclusion_tag("preparation/participant_workspace.html", takes_context=True)
def participant_preparation_workspace(context, journey):
    actor = context["request"].user
    form_requests = list(journey.form_requests.all())
    resources = resources_for_journey(journey=journey, actor=actor)
    return {
        "journey": journey,
        "form_requests": form_requests,
        "resources": resources,
    }

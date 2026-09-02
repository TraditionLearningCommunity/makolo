from django import template

from sharing.document_services import can_export_journey_artifact


register = template.Library()


@register.simple_tag
def can_export_artifact(user, artifact):
    return can_export_journey_artifact(user, artifact, channel="download").allowed

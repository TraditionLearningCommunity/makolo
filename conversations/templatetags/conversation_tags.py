from django import template

from conversations.attention import attention_points_for_profile, conversation_attention_count
from conversations.form_services import form_request_for_profile
from conversations.point_models import ConversationPoint
from conversations.presentation import conversation_context_label


register = template.Library()


@register.simple_tag
def conversation_attention_badge(profile):
    if not getattr(profile, "is_authenticated", False):
        return 0
    return conversation_attention_count(profile)


@register.simple_tag
def conversation_attention_preview(profile, limit=5):
    if not getattr(profile, "is_authenticated", False):
        return []
    items = attention_points_for_profile(profile, limit=int(limit))
    point_ids = [item.point_id for item in items]
    points = {
        point.pk: point
        for point in ConversationPoint.objects.filter(pk__in=point_ids).select_related(
            "conversation",
            "conversation__context__space",
            "conversation__context__group",
            "conversation__context__activity",
            "conversation__context__occurrence__activity",
            "conversation__context__dossier",
            "conversation__context__project",
            "conversation__context__journey__activity",
            "conversation__context__action_proposal__need",
            "conversation__context__direct_profile_a",
            "conversation__context__direct_profile_b",
        )
    }
    return [
        {
            "attention": item,
            "point": points[item.point_id],
            "context_label": conversation_context_label(points[item.point_id].conversation, profile),
        }
        for item in items
        if item.point_id in points
    ]


@register.simple_tag
def conversation_point_form_request(point, profile):
    return form_request_for_profile(point, profile)

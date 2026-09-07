from django import template

from conversations.attention import attention_points_for_profile, conversation_attention_count
from conversations.point_models import ConversationPoint


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
        for point in ConversationPoint.objects.filter(pk__in=point_ids).select_related("conversation", "conversation__context")
    }
    return [{"attention": item, "point": points.get(item.point_id)} for item in items if item.point_id in points]

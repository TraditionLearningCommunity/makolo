from django import template

from conversations.attention import attention_points_for_profile, conversation_attention_badge_count
from conversations.form_services import form_request_for_profile
from conversations.point_models import ConversationPoint
from conversations.presentation import conversation_context_label
from core.web.request_context import get_request_context


register = template.Library()


@register.simple_tag(takes_context=True)
def conversation_attention_badge(context, profile):
    if not getattr(profile, "is_authenticated", False):
        return 0
    request = context.get("request")
    if request is None:
        return conversation_attention_badge_count(profile)
    request_context = get_request_context(request)
    if not request_context.surface.needs_capability("conversation_attention"):
        return 0
    return request_context.memoize(
        ("conversation_attention", profile.pk),
        lambda: conversation_attention_badge_count(
            profile,
            at=request_context.observed_at,
        ),
    )


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

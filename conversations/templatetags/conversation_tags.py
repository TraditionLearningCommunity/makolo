from django.core.exceptions import ObjectDoesNotExist
from django import template

from conversations.attention import attention_points_for_profile, conversation_attention_badge_count, has_conversation_attention
from conversations.form_services import form_request_for_profile
from conversations.point_models import ConversationPoint
from conversations.presentation import conversation_context_label, conversations_for_context, visible_exchange_entries_for_profile
from conversations.composing import can_ensure_context_conversation
from core.web.request_context import get_request_context


register = template.Library()


@register.simple_tag(takes_context=True)
def conversation_attention_signal(context, profile):
    if not getattr(profile, "is_authenticated", False):
        return False
    request = context.get("request")
    if request is None:
        return has_conversation_attention(profile)
    request_context = get_request_context(request)
    if not request_context.surface.needs_capability("conversation_attention"):
        return False
    return request_context.memoize(
        ("conversation_attention", "presence", profile.pk),
        lambda: has_conversation_attention(profile, at=request_context.observed_at),
    )


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


@register.simple_tag
def conversation_context_entry(profile, kind, context_pk):
    """Whether an existing, visible Conversation can be entered from context."""
    if not getattr(profile, "is_authenticated", False) or not context_pk:
        return False
    try:
        return bool(conversations_for_context(profile, kind, str(context_pk)))
    except (ValueError, TypeError):
        return False


@register.simple_tag
def conversation_context_can_ensure(profile, kind, context_pk):
    if not getattr(profile, "is_authenticated", False) or not context_pk:
        return False
    return can_ensure_context_conversation(profile, kind, str(context_pk))


@register.simple_tag
def conversation_point_exchange_preview(point, profile):
    return visible_exchange_entries_for_profile(profile, point, limit=5)



@register.simple_tag
def conversation_point_attachments(point, profile):
    from conversations.rich_services import visible_attachments_for_profile
    return [
        item for item in visible_attachments_for_profile(profile, point)
        if item.exchange_entry_id is None
    ]


@register.simple_tag
def conversation_point_media_sections(point, profile):
    """One ACL-filtered semantic projection for a Web Point.

    Point media, ordered Poll assertions and response media must not be
    flattened into one trailing collection. Never expose another respondent
    through their file without the canonical owner permission.
    """
    from conversations.rich_services import visible_attachments_for_profile
    from conversations.semantic_media import response_media_label
    visible = visible_attachments_for_profile(profile, point, limit=100)
    root, option_map, response_map = [], {}, {}
    for attachment in visible:
        if attachment.exchange_entry_id:
            continue
        if attachment.response_id:
            response_map.setdefault(str(attachment.response_id), []).append(attachment)
        elif attachment.option_id:
            option_map.setdefault(str(attachment.option_id), []).append(attachment)
        else:
            root.append(attachment)
    choices = [
        {"id": str(option.pk), "label": option.label,
         "files": option_map.get(str(option.pk), [])}
        for option in point.options.all()
    ]
    return {
        "root": root,
        "choices": choices,
        "responses": [
            {"label": response_media_label(point, media[0].response), "files": media}
            for media in response_map.values() if media
        ],
    }


@register.simple_tag
def conversation_exchange_attachments(entry, profile):
    from conversations.media_services import can_download_attachment
    return [
        item for item in entry.attachments.all()
        if can_download_attachment(profile, item)
    ]


@register.simple_tag
def conversation_visible_successor(point, profile):
    """A replaced Point never reveals the identity of a private successor."""
    from conversations.point_services import point_visible_to
    if point.lifecycle != "superseded" or not getattr(profile, "is_authenticated", False):
        return None
    for candidate in point.superseded_by_points.order_by("-published_at", "-created_at")[:5]:
        if point_visible_to(profile, candidate):
            return candidate
    return None


@register.simple_tag
def conversation_visible_resolution(point, profile):
    """Use the same result-audience projection as the API and search."""
    from conversations.point_services import point_resolution_visible_to
    if point.lifecycle != "resolved" or not getattr(profile, "is_authenticated", False):
        return None
    if not point_resolution_visible_to(profile, point):
        return None
    try:
        return point.resolution.summary or None
    except ObjectDoesNotExist:
        return None


@register.simple_tag
def conversation_media_label(kind):
    """Only labels for media/Point kinds the server actually confirmed visible."""
    return {
        "voice": "Vocal",
        "audio": "Audio",
        "image": "Photo",
        "video": "Vidéo",
        "file": "Document",
        "poll": "Sondage",
        "form": "Formulaire",
        "confirmation": "Confirmation",
        "exchange": "Échanges",
    }.get(kind, "Contenu")

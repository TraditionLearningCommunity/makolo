from django import template

from notifications.selectors import get_unread_notifications_count


register = template.Library()


@register.simple_tag
def unread_notifications_count(user):
    return get_unread_notifications_count(user)

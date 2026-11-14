"""Stable, owner-scoped continuation for the notification inbox."""
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from notifications.models import Notification


class NotificationCursorPagination(CursorPagination):
    page_size = 15
    ordering = ("-created_at", "-id")

    def get_paginated_response(self, data):
        owner = Notification.objects.filter(recipient=self.request.user)
        unread = owner.filter(read_at__isnull=True).count()
        total = owner.count()
        filtered = unread if self.request.query_params.get("filter") == "unread" else total
        return Response({
            "count": filtered,
            "total_count": total,
            "unread_count": unread,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })

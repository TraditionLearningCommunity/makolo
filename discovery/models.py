import uuid

from django.conf import settings
from django.db import models


class EventBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_bookmarks",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="disc_bookmark_user_event_uq",
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="disc_bookmark_user_idx"),
            models.Index(fields=["event", "created_at"], name="disc_bookmark_event_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.event}"

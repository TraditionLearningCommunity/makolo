import uuid

from django.conf import settings
from django.db import models


class ActivityBookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_bookmarks",
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "activity"],
                name="disc_bm_user_activity_uq",
            )
        ]
        indexes = [
            models.Index(fields=["user", "created_at"], name="disc_bm_user_created_idx"),
            models.Index(fields=["activity", "created_at"], name="disc_bm_activity_created_idx"),
        ]

    def __str__(self):
        return f"{self.user} — {self.activity}"

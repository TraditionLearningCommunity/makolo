import uuid

from django.conf import settings
from django.db import models


class Topic(models.Model):
    """Canonical, reusable vocabulary for explicit interests and content topics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label", "code"]
        indexes = [models.Index(fields=["is_active", "label"], name="topic_active_label_idx")]

    def __str__(self):
        return self.label


class ProfileInterest(models.Model):
    """An explicit interest declared by a Profile.

    Rows in this table are declarations only. Search history, bookmarks, follows,
    journeys and other inferred signals must never be materialized here silently.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_interests",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="profile_interests",
    )
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "topic"],
                name="topics_profile_interest_unique",
            )
        ]
        indexes = [
            models.Index(fields=["profile", "is_public"], name="topic_pi_prof_public_idx"),
        ]

    def __str__(self):
        return f"{self.profile} — {self.topic}"


class ActivityTopic(models.Model):
    """Explicit Activity↔Topic classification using the canonical Topic vocabulary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="topic_links",
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="activity_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "topic"],
                name="topics_activity_topic_unique",
            )
        ]
        indexes = [models.Index(fields=["topic", "activity"], name="topic_at_topic_act_idx")]

    def __str__(self):
        return f"{self.activity} — {self.topic}"

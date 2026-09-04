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
    """An explicit interest declared by a Profile; never inferred from behavior."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_interests")
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="profile_interests")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["profile", "topic"], name="topics_profile_interest_unique")]
        indexes = [models.Index(fields=["profile", "is_public"], name="topic_pi_prof_public_idx")]

    def __str__(self):
        return f"{self.profile} — {self.topic}"


class OpenToKind(models.TextChoices):
    PARTICIPATE = "participate", "Participer"
    COLLABORATE = "collaborate", "Collaborer"
    VOLUNTEER = "volunteer", "Bénévolat"
    SPEAK = "speak", "Intervenir / prendre la parole"
    MENTOR = "mentor", "Mentorat"
    ORGANIZE = "organize", "Organiser"
    OPPORTUNITIES = "opportunities", "Recevoir des opportunités"


class ProfileOpenTo(models.Model):
    """Voluntary solicitation preference, distinct from ProfileInterest."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="open_to_declarations")
    kind = models.CharField(max_length=32, choices=OpenToKind.choices)
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="open_to_declarations", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)
    is_searchable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["profile", "kind", "topic"], name="topics_profile_open_to_unique")]
        indexes = [
            models.Index(fields=["profile", "is_active", "is_public"], name="topic_pot_prof_public_idx"),
            models.Index(fields=["is_active", "is_searchable"], name="topic_pot_search_idx"),
        ]

    def __str__(self):
        suffix = f" — {self.topic}" if self.topic_id else ""
        return f"{self.profile} — {self.get_kind_display()}{suffix}"


class ActivityTopic(models.Model):
    """Explicit Activity↔Topic classification using the canonical Topic vocabulary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="topic_links")
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="activity_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["activity", "topic"], name="topics_activity_topic_unique")]
        indexes = [models.Index(fields=["topic", "activity"], name="topic_at_topic_act_idx")]

    def __str__(self):
        return f"{self.activity} — {self.topic}"

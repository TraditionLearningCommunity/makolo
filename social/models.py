import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ContributionKind(models.TextChoices):
    UPDATE = "update", "Mise à jour officielle"
    TIP = "tip", "Conseil"
    FIELD_NOTE = "field_note", "Note terrain"
    DISCUSSION = "discussion", "Discussion"
    SHARE = "share", "Partage d'Activity"


class ContributionVisibility(models.TextChoices):
    PUBLIC = "public", "Publique"
    CONTEXT = "context", "Contexte autorisé"


class ContributionStatus(models.TextChoices):
    PUBLISHED = "published", "Publiée"
    HIDDEN = "hidden", "Masquée"
    REMOVED = "removed", "Retirée"


class Contribution(models.Model):
    """UGC anchored to canonical Makolo contexts.

    The model deliberately stores references, not copied Activity/Space/Group
    facts. A Contribution can never be a context-free social post.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="social_contributions",
    )
    kind = models.CharField(max_length=24, choices=ContributionKind.choices)
    body = models.TextField(max_length=2400, blank=True)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.PROTECT,
        related_name="social_contributions",
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="replies",
        null=True,
        blank=True,
    )
    visibility = models.CharField(
        max_length=16,
        choices=ContributionVisibility.choices,
        default=ContributionVisibility.CONTEXT,
    )
    status = models.CharField(
        max_length=16,
        choices=ContributionStatus.choices,
        default=ContributionStatus.PUBLISHED,
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderated_social_contributions",
        null=True,
        blank=True,
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_reason = models.CharField(max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(space__isnull=False)
                    | Q(group__isnull=False)
                    | Q(activity__isnull=False)
                    | Q(occurrence__isnull=False)
                ),
                name="social_contribution_has_context",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="social_status_created_idx"),
            models.Index(fields=["group", "status", "created_at"], name="social_group_stream_idx"),
            models.Index(fields=["activity", "status", "created_at"], name="social_activity_stream_idx"),
            models.Index(fields=["space", "status", "created_at"], name="social_space_stream_idx"),
            models.Index(fields=["author_profile", "created_at"], name="social_author_created_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.body = (self.body or "").strip()
        self.moderation_reason = (self.moderation_reason or "").strip()
        if not any((self.space_id, self.group_id, self.activity_id, self.occurrence_id)):
            errors["activity"] = "Une Contribution doit être ancrée dans un contexte Makolo."
        if self.kind != ContributionKind.SHARE and not self.body:
            errors["body"] = "Le texte de la Contribution est obligatoire."
        if self.kind == ContributionKind.SHARE and not (self.group_id and self.activity_id):
            errors["kind"] = "Un partage interne doit référencer un Groupe et une Activity."
        if self.group_id and self.visibility == ContributionVisibility.PUBLIC:
            errors["visibility"] = "Le contenu d'un Groupe reste limité aux personnes autorisées."
        if self.occurrence_id:
            if not self.activity_id:
                errors["activity"] = "Une Contribution liée à une Occurrence doit référencer son Activity."
            elif self.occurrence.activity_id != self.activity_id:
                errors["occurrence"] = "L'Occurrence doit appartenir à la même Activity."
        if self.space_id and self.activity_id and self.activity.space_id and self.activity.space_id != self.space_id:
            errors["space"] = "L'Espace explicite doit être cohérent avec l'Activity."
        if self.group_id and self.space_id and self.group.space_id and self.group.space_id != self.space_id:
            errors["space"] = "L'Espace explicite doit être cohérent avec le Groupe."
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "Une Contribution ne peut pas se répondre à elle-même."
            if self.parent.parent_id:
                errors["parent"] = "Les discussions Makolo sont limitées à une profondeur de réponse."
            for field in ("space_id", "group_id", "activity_id", "occurrence_id", "visibility"):
                if getattr(self, field) != getattr(self.parent, field):
                    errors["parent"] = "Une réponse doit conserver exactement le contexte de la Contribution racine."
                    break
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = Contribution.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de modération pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def is_reply(self):
        return self.parent_id is not None

    def __str__(self):
        return f"{self.get_kind_display()} — {self.author_profile}"

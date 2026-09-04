import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from topics.models import OpenToKind


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


class ActionNeedStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    CLOSED = "closed", "Fermé"


class ActionNeed(models.Model):
    """A lightweight bilateral-network need: "I am looking for people for this"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_action_needs",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_action_needs",
    )
    title = models.CharField(max_length=220)
    description = models.CharField(max_length=600, blank=True)
    open_to_kind = models.CharField(max_length=32, choices=OpenToKind.choices)
    topics = models.ManyToManyField("topics.Topic", related_name="action_needs", blank=True)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    opportunity = models.ForeignKey(
        "opportunities.Opportunity",
        on_delete=models.PROTECT,
        related_name="action_needs",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=ActionNeedStatus.choices, default=ActionNeedStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(owner_profile__isnull=False, space__isnull=True)
                    | Q(owner_profile__isnull=True, space__isnull=False)
                ),
                name="social_action_need_single_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["owner_profile", "status", "created_at"], name="social_need_profile_idx"),
            models.Index(fields=["space", "status", "created_at"], name="social_need_space_idx"),
            models.Index(fields=["status", "open_to_kind"], name="social_need_open_to_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        if bool(self.owner_profile_id) == bool(self.space_id):
            errors["owner_profile"] = "Un besoin appartient soit à un Profile, soit à un Space, jamais aux deux."
        if self.activity_id:
            if self.owner_profile_id and self.activity.owner_profile_id != self.owner_profile_id:
                errors["activity"] = "L'Activity doit appartenir au même Profile que le besoin."
            if self.space_id and self.activity.space_id != self.space_id:
                errors["activity"] = "L'Activity doit appartenir au même Space que le besoin."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ActionNeed.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service ActionNeed pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def owner_display_name(self):
        if self.space_id:
            return self.space.name
        if self.owner_profile_id:
            return self.owner_profile.full_name or self.owner_profile.username
        return ""

    def __str__(self):
        return self.title


class ProfileSolicitationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACCEPTED = "accepted", "Acceptée"
    DECLINED = "declined", "Refusée"
    CANCELLED = "cancelled", "Annulée"


class ProfileSolicitation(models.Model):
    """Explicit presentation of one ActionNeed to one discoverable Profile."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    need = models.ForeignKey(ActionNeed, on_delete=models.PROTECT, related_name="solicitations")
    recipient_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_profile_solicitations",
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_profile_solicitations",
    )
    status = models.CharField(
        max_length=16,
        choices=ProfileSolicitationStatus.choices,
        default=ProfileSolicitationStatus.PENDING,
    )
    message = models.CharField(max_length=500, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["need", "recipient_profile"],
                condition=Q(status=ProfileSolicitationStatus.PENDING),
                name="social_solicitation_unique_pending",
            ),
        ]
        indexes = [
            models.Index(fields=["need", "status", "created_at"], name="social_sol_need_status_idx"),
            models.Index(fields=["recipient_profile", "status", "created_at"], name="social_sol_recipient_idx"),
            models.Index(fields=["sent_by", "status", "created_at"], name="social_sol_sender_idx"),
        ]

    def clean(self):
        super().clean()
        self.message = (self.message or "").strip()
        errors = {}
        if self.need_id and self.need.owner_profile_id and self.need.owner_profile_id == self.recipient_profile_id:
            errors["recipient_profile"] = "Un besoin personnel ne peut pas être sollicité auprès de son propre propriétaire."
        if self._state.adding and self.need_id and self.need.status != ActionNeedStatus.OPEN:
            errors["need"] = "Une nouvelle sollicitation exige un besoin ouvert."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ProfileSolicitation.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service ProfileSolicitation pour répondre ou annuler."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    def __str__(self):
        return f"{self.need} → {self.recipient_profile} ({self.get_status_display()})"

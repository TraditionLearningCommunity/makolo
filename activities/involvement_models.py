import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ActivityInvolvementStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    REMOVED = "removed", "Retiré"


class ActivityInvolvementVisibility(models.TextChoices):
    CONTEXT = "context", "Contexte autorisé"
    PUBLIC = "public", "Public"


class ActivityInvolvementExternalKind(models.TextChoices):
    PERSON = "person", "Personne externe"
    SPACE = "space", "Organisation externe"


class ActivityInvolvementConfirmationBasis(models.TextChoices):
    PROFILE_CONFIRMED = "profile_confirmed", "Confirmé par le Profile"
    SPACE_CONFIRMED = "space_confirmed", "Confirmé par le Space"
    ORGANIZER_DECLARED = "organizer_declared", "Annoncé par l'organisateur"


class ActivityInvolvementFunctionKind(models.TextChoices):
    PERFORMER = "performer", "Artiste / performer"
    SPEAKER = "speaker", "Intervenant"
    MODERATOR = "moderator", "Modération"
    FACILITATOR = "facilitator", "Facilitation"
    GUEST = "guest", "Invité"
    MENTOR = "mentor", "Mentor"
    JURY = "jury", "Jury"
    VOLUNTEER = "volunteer", "Bénévole"
    STAFF = "staff", "Équipe"
    PROVIDER = "provider", "Prestataire"
    PARTNER = "partner", "Partenaire"
    SPONSOR = "sponsor", "Sponsor"
    CO_ORGANIZER = "co_organizer", "Co-organisateur"
    OTHER = "other", "Autre"


class ActivityInvolvement(models.Model):
    """A real contextual involvement in an Activity, optionally one Occurrence.

    This is descriptive participation/presentation truth. It never grants
    Permission, Mandate, Access or operational Assignment.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        "activities.Activity",
        on_delete=models.CASCADE,
        related_name="involvements",
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence",
        on_delete=models.CASCADE,
        related_name="involvements",
        null=True,
        blank=True,
    )
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="activity_involvements",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="activity_involvements",
        null=True,
        blank=True,
    )
    external_kind = models.CharField(
        max_length=16,
        choices=ActivityInvolvementExternalKind.choices,
        blank=True,
        default="",
    )
    external_display_name = models.CharField(max_length=220, blank=True)
    contextual_title = models.CharField(max_length=220, blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=ActivityInvolvementVisibility.choices,
        default=ActivityInvolvementVisibility.CONTEXT,
    )
    confirmation_basis = models.CharField(
        max_length=24,
        choices=ActivityInvolvementConfirmationBasis.choices,
    )
    source_proposal = models.OneToOneField(
        "social.ActionProposal",
        on_delete=models.PROTECT,
        related_name="activity_involvement",
        null=True,
        blank=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_activity_involvements",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_activity_involvements",
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=ActivityInvolvementStatus.choices,
        default=ActivityInvolvementStatus.ACTIVE,
    )
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="removed_activity_involvements",
        null=True,
        blank=True,
    )
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity_id", "occurrence_id", "created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(profile__isnull=False, space__isnull=True, external_kind="")
                    | Q(profile__isnull=True, space__isnull=False, external_kind="")
                    | Q(profile__isnull=True, space__isnull=True, external_kind__in=["person", "space"])
                ),
                name="activities_involvement_single_subject",
            ),
        ]
        indexes = [
            models.Index(fields=["activity", "status", "visibility"], name="activities_inv_activity_idx"),
            models.Index(fields=["occurrence", "status", "visibility"], name="activities_inv_occ_idx"),
            models.Index(fields=["profile", "activity"], name="activities_inv_profile_idx"),
            models.Index(fields=["space", "activity"], name="activities_inv_space_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.external_display_name = (self.external_display_name or "").strip()
        self.contextual_title = (self.contextual_title or "").strip()
        self.short_description = (self.short_description or "").strip()
        internal_count = int(bool(self.profile_id)) + int(bool(self.space_id))
        external = bool(self.external_kind)
        if internal_count + int(external) != 1:
            errors["profile"] = "Une implication vise exactement un Profile, un Space ou une identité externe."
        if external and not self.external_display_name:
            errors["external_display_name"] = "Une identité externe exige un nom d'affichage."
        if not external and self.external_display_name:
            errors["external_display_name"] = "Le nom externe ne doit pas dupliquer une identité Makolo liée."
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L'Occurrence doit appartenir à la même Activity."
        if self.confirmation_basis == ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED and not self.profile_id:
            errors["confirmation_basis"] = "Une confirmation Profile exige un Profile lié."
        if self.confirmation_basis == ActivityInvolvementConfirmationBasis.SPACE_CONFIRMED and not self.space_id:
            errors["confirmation_basis"] = "Une confirmation Space exige un Space lié."
        if self.confirmation_basis == ActivityInvolvementConfirmationBasis.ORGANIZER_DECLARED and not external:
            errors["confirmation_basis"] = "Une déclaration organisateur est réservée aux identités externes."
        if self.status == ActivityInvolvementStatus.REMOVED and not self.removed_at:
            errors["removed_at"] = "Une implication retirée doit conserver sa date de retrait."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = ActivityInvolvement.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service ActivityInvolvement pour changer cet état."})
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

    @property
    def display_name(self):
        if self.profile_id:
            return self.profile.full_name or self.profile.username
        if self.space_id:
            return self.space.name
        return self.external_display_name


class ActivityInvolvementFunction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    involvement = models.ForeignKey(
        ActivityInvolvement,
        on_delete=models.CASCADE,
        related_name="functions",
    )
    kind = models.CharField(max_length=24, choices=ActivityInvolvementFunctionKind.choices)
    label = models.CharField(max_length=180, blank=True)
    presentation_tier = models.PositiveSmallIntegerField(default=3)
    presentation_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["presentation_tier", "presentation_order", "kind", "id"]
        constraints = [
            models.UniqueConstraint(fields=["involvement", "kind"], name="activities_inv_function_unique"),
            models.CheckConstraint(condition=Q(presentation_tier__gte=1, presentation_tier__lte=5), name="activities_inv_tier_valid"),
        ]
        indexes = [
            models.Index(fields=["kind", "presentation_tier"], name="activities_inv_func_kind_idx"),
        ]

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()
        if not 1 <= self.presentation_tier <= 5:
            raise ValidationError({"presentation_tier": "Le niveau de présentation doit être compris entre 1 et 5."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ActivityInvolvementNeedConfig(models.Model):
    """Activity-owned realization policy for an ActionNeed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    need = models.OneToOneField(
        "social.ActionNeed",
        on_delete=models.CASCADE,
        related_name="activity_involvement_config",
    )
    function_kind = models.CharField(max_length=24, choices=ActivityInvolvementFunctionKind.choices)
    function_label = models.CharField(max_length=180, blank=True)
    result_visibility = models.CharField(
        max_length=16,
        choices=ActivityInvolvementVisibility.choices,
        default=ActivityInvolvementVisibility.CONTEXT,
    )
    presentation_tier = models.PositiveSmallIntegerField(default=3)
    presentation_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(presentation_tier__gte=1, presentation_tier__lte=5), name="activities_inv_need_tier_valid"),
        ]

    def clean(self):
        super().clean()
        self.function_label = (self.function_label or "").strip()
        errors = {}
        if self.need_id and not self.need.activity_id:
            errors["need"] = "Une configuration d'implication exige un besoin lié à une Activity."
        if self.need_id and self.need.occurrence_id and self.need.occurrence.activity_id != self.need.activity_id:
            errors["need"] = "L'Occurrence du besoin doit appartenir à son Activity."
        if not 1 <= self.presentation_tier <= 5:
            errors["presentation_tier"] = "Le niveau de présentation doit être compris entre 1 et 5."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

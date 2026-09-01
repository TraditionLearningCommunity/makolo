import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .enums import PresentationPurpose, PresentationState, Provenance, VersionStatus, Visibility


class PresentationTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=160)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    provenance = models.CharField(max_length=16, choices=Provenance.choices)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    owner_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presentation_templates", null=True, blank=True)
    owner_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="presentation_templates", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_presentation_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(owner_profile__isnull=False, owner_space__isnull=False), name="mps_template_single_owner"),
            models.UniqueConstraint(fields=["owner_profile", "slug"], condition=Q(owner_profile__isnull=False), name="mps_template_profile_slug_unique"),
            models.UniqueConstraint(fields=["owner_space", "slug"], condition=Q(owner_space__isnull=False), name="mps_template_space_slug_unique"),
            models.UniqueConstraint(fields=["slug"], condition=Q(provenance=Provenance.MAKOLO), name="mps_template_makolo_slug_unique"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.provenance == Provenance.MAKOLO and (self.owner_profile_id or self.owner_space_id):
            errors["provenance"] = "Un modèle Makolo ne porte pas de propriétaire utilisateur ou Espace."
        elif self.provenance == Provenance.USER and not self.owner_profile_id:
            errors["owner_profile"] = "Un modèle utilisateur exige un propriétaire Profil."
        elif self.provenance == Provenance.SPACE and not self.owner_space_id:
            errors["owner_space"] = "Un modèle Espace exige un propriétaire Espace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class _ImmutablePublishedVersion(models.Model):
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=VersionStatus.choices, default=VersionStatus.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values("status", *self.immutable_fields).first()
            if previous and previous["status"] == VersionStatus.PUBLISHED:
                for field in self.immutable_fields:
                    if previous[field] != getattr(self, field):
                        raise ValidationError("Une version publiée est immuable.")
        if self.status == VersionStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)


class PresentationTemplateVersion(_ImmutablePublishedVersion):
    template = models.ForeignKey(PresentationTemplate, on_delete=models.PROTECT, related_name="versions")
    schema_version = models.PositiveSmallIntegerField(default=1)
    manifest = models.JSONField(default=dict)
    immutable_fields = ("schema_version", "manifest", "version_number")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["template", "version_number"], name="mps_template_version_unique")]

    def clean(self):
        super().clean()
        if self.version_number < 1:
            raise ValidationError({"version_number": "La version doit être positive."})
        if self.status in {VersionStatus.SUBMITTED, VersionStatus.PUBLISHED}:
            from .manifests.validation import validate_manifest
            validate_manifest(self.manifest)


class PresentationTheme(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=160)
    name = models.CharField(max_length=180)
    provenance = models.CharField(max_length=16, choices=Provenance.choices)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    owner_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="presentation_themes", null=True, blank=True)
    owner_space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="presentation_themes", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_presentation_themes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(owner_profile__isnull=False, owner_space__isnull=False), name="mps_theme_single_owner")]

    def clean(self):
        super().clean()
        if self.provenance == Provenance.MAKOLO and (self.owner_profile_id or self.owner_space_id):
            raise ValidationError("Un thème Makolo ne porte pas de propriétaire.")
        if self.provenance == Provenance.USER and not self.owner_profile_id:
            raise ValidationError({"owner_profile": "Un thème utilisateur exige un Profil."})
        if self.provenance == Provenance.SPACE and not self.owner_space_id:
            raise ValidationError({"owner_space": "Un thème Espace exige un Espace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PresentationThemeVersion(_ImmutablePublishedVersion):
    theme = models.ForeignKey(PresentationTheme, on_delete=models.PROTECT, related_name="versions")
    schema_version = models.PositiveSmallIntegerField(default=1)
    tokens = models.JSONField(default=dict)
    immutable_fields = ("schema_version", "tokens", "version_number")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["theme", "version_number"], name="mps_theme_version_unique")]

    def clean(self):
        super().clean()
        from .themes import validate_theme_tokens
        validate_theme_tokens(self.tokens)


class ActivityPresentation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("activities.Activity", on_delete=models.CASCADE, related_name="presentations")
    occurrence = models.ForeignKey("activities.Occurrence", on_delete=models.CASCADE, related_name="presentations", null=True, blank=True)
    purpose = models.CharField(max_length=24, choices=PresentationPurpose.choices)
    template_version = models.ForeignKey(PresentationTemplateVersion, on_delete=models.PROTECT, related_name="activity_bindings")
    theme_version = models.ForeignKey(PresentationThemeVersion, on_delete=models.PROTECT, related_name="activity_bindings")
    editorial_data = models.JSONField(default=dict, blank=True)
    visual_overrides = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=16, choices=PresentationState.choices, default=PresentationState.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_activity_presentations")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["activity", "purpose"], condition=Q(occurrence__isnull=True), name="mps_activity_purpose_unique"),
            models.UniqueConstraint(fields=["occurrence", "purpose"], condition=Q(occurrence__isnull=False), name="mps_occurrence_purpose_unique"),
        ]
        indexes = [models.Index(fields=["activity", "purpose", "state"], name="mps_activity_purpose_state_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity."
        from .editorial import validate_editorial_data
        try:
            validate_editorial_data(self.purpose, self.editorial_data)
        except ValidationError as exc:
            errors["editorial_data"] = exc.messages
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.state == PresentationState.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        return super().save(*args, **kwargs)

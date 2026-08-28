import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from geography.validators import validate_timezone_name


class OpportunityKind(models.TextChoices):
    JOB = "job", "Emploi"
    SCHOLARSHIP = "scholarship", "Bourse"
    INTERNSHIP = "internship", "Stage"
    EDUCATION = "education", "Études"
    GRANT = "grant", "Financement"
    COMPETITION = "competition", "Concours"
    PROGRAM = "program", "Programme"
    VOLUNTEERING = "volunteering", "Volontariat"
    OTHER = "other", "Autre"


class OpportunityPublicationStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    WITHDRAWN = "withdrawn", "Retirée"
    ARCHIVED = "archived", "Archivée"
    MERGED = "merged", "Fusionnée"


class Opportunity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=OpportunityKind.choices)
    publication_status = models.CharField(max_length=16, choices=OpportunityPublicationStatus.choices, default=OpportunityPublicationStatus.DRAFT)
    current_revision = models.ForeignKey("OpportunityRevision", on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    merged_into = models.ForeignKey("self", on_delete=models.PROTECT, related_name="merged_duplicates", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_opportunities", null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(publication_status=OpportunityPublicationStatus.MERGED, merged_into__isnull=False) | (~Q(publication_status=OpportunityPublicationStatus.MERGED) & Q(merged_into__isnull=True))),
                name="opp_merged_target_consistent",
            ),
            models.CheckConstraint(condition=Q(merged_into__isnull=True) | ~Q(id=models.F("merged_into")), name="opp_merge_not_self"),
        ]
        indexes = [
            models.Index(fields=["publication_status", "kind"], name="opp_status_kind_idx"),
            models.Index(fields=["current_revision"], name="opp_current_revision_idx"),
            models.Index(fields=["merged_into"], name="opp_merged_into_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        merged = self.publication_status == OpportunityPublicationStatus.MERGED
        if merged and not self.merged_into_id:
            errors["merged_into"] = "Une Opportunity fusionnée doit référencer sa cible canonique."
        if not merged and self.merged_into_id:
            errors["merged_into"] = "Seule une Opportunity fusionnée peut référencer une cible canonique."
        if self.pk and self.merged_into_id == self.pk:
            errors["merged_into"] = "Une Opportunity ne peut pas être fusionnée vers elle-même."
        if self.current_revision_id and self.current_revision.opportunity_id != self.pk:
            errors["current_revision"] = "La révision courante doit appartenir à cette Opportunity."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_lifecycle_transition", False):
            previous = Opportunity.objects.filter(pk=self.pk).values("publication_status", "current_revision_id", "merged_into_id", "published_at").first()
            current = {"publication_status": self.publication_status, "current_revision_id": self.current_revision_id, "merged_into_id": self.merged_into_id, "published_at": self.published_at}
            if previous and previous != current:
                raise ValidationError("Utilisez les services Opportunity pour modifier le lifecycle éditorial.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_lifecycle_transition = False
        return result

    def delete(self, *args, **kwargs):
        if self.publication_status != OpportunityPublicationStatus.DRAFT or self.revisions.exists():
            raise ValidationError("Une Opportunity historique ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        title = getattr(self.current_revision, "title", "") if self.current_revision_id else ""
        return title or f"Opportunity {self.pk}"


class OpportunityRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="revisions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    summary = models.TextField(blank=True)
    issuer_name = models.CharField(max_length=220)
    opens_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=100, validators=[validate_timezone_name])
    application_instructions = models.TextField(blank=True)
    remote_allowed = models.BooleanField(null=True, blank=True)
    change_summary = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_opportunity_revisions", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["opportunity", "version"]
        constraints = [
            models.UniqueConstraint(fields=["opportunity", "version"], name="opp_revision_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="opp_revision_version_positive"),
        ]
        indexes = [
            models.Index(fields=["opportunity", "version"], name="opp_revision_lookup_idx"),
            models.Index(fields=["opens_at"], name="opp_revision_opens_idx"),
            models.Index(fields=["deadline_at"], name="opp_revision_deadline_idx"),
        ]

    def clean(self):
        super().clean()
        self.timezone = (self.timezone or "").strip()
        if self.opens_at and self.deadline_at and self.deadline_at <= self.opens_at:
            raise ValidationError({"deadline_at": "La deadline doit être postérieure à l’ouverture."})

    def save(self, *args, **kwargs):
        if self._state.adding and self.published_at and not getattr(self, "_allow_publication", False):
            raise ValidationError("Une révision est publiée via le service de publication.")
        if self.pk and not self._state.adding:
            previous = OpportunityRevision.objects.filter(pk=self.pk).values("opportunity_id", "version", "title", "summary", "issuer_name", "opens_at", "deadline_at", "timezone", "application_instructions", "remote_allowed", "change_summary", "published_at").first()
            if previous and previous["published_at"] is not None:
                current = {"opportunity_id": self.opportunity_id, "version": self.version, "title": self.title, "summary": self.summary, "issuer_name": self.issuer_name, "opens_at": self.opens_at, "deadline_at": self.deadline_at, "timezone": self.timezone, "application_instructions": self.application_instructions, "remote_allowed": self.remote_allowed, "change_summary": self.change_summary, "published_at": self.published_at}
                if previous != current:
                    raise ValidationError("Une OpportunityRevision publiée est définitivement immuable.")
            elif previous and self.published_at is not None and not getattr(self, "_allow_publication", False):
                raise ValidationError("Une révision est publiée via le service de publication.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_publication = False
        return result

    def delete(self, *args, **kwargs):
        persisted = OpportunityRevision.objects.filter(pk=self.pk).values_list("published_at", flat=True).first()
        if persisted is not None:
            raise ValidationError("Une OpportunityRevision publiée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)

    def temporal_state(self, *, at=None):
        at = at or timezone.now()
        if self.opens_at is not None and self.opens_at > at:
            return "upcoming"
        if self.deadline_at is not None and self.deadline_at <= at:
            return "closed"
        return "open"

    def __str__(self):
        return f"{self.title} — v{self.version}"


class OpportunityZoneRole(models.TextChoices):
    LOCATION = "location", "Localisation"
    ELIGIBILITY = "eligibility", "Éligibilité"


class OpportunityZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(OpportunityRevision, on_delete=models.CASCADE, related_name="zones")
    zone = models.ForeignKey("geography.Zone", on_delete=models.PROTECT, related_name="opportunity_relations")
    role = models.CharField(max_length=16, choices=OpportunityZoneRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["revision", "zone", "role"], name="opp_zone_revision_role_unique")]
        indexes = [models.Index(fields=["zone", "role"], name="opp_zone_role_idx")]

    def clean(self):
        super().clean()
        if self.revision_id and OpportunityRevision.objects.filter(pk=self.revision_id, published_at__isnull=False).exists():
            raise ValidationError({"revision": "Les zones d’une révision publiée sont immuables."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.revision.published_at is not None:
            raise ValidationError("Les zones d’une révision publiée sont immuables.")
        return super().delete(*args, **kwargs)


class OpportunitySourceType(models.TextChoices):
    OFFICIAL = "official", "Officielle"
    TRUSTED_PARTNER = "trusted_partner", "Partenaire de confiance"
    AGGREGATOR = "aggregator", "Agrégateur"
    USER_SUPPLIED = "user_supplied", "Fournie par un utilisateur"


class OpportunitySourceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CHANGED = "changed", "Modifiée"
    UNREACHABLE = "unreachable", "Inaccessible"
    REMOVED = "removed", "Supprimée à la source"


class OpportunitySource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=24, choices=OpportunitySourceType.choices)
    source_name = models.CharField(max_length=220)
    url = models.URLField(max_length=1000)
    external_reference = models.CharField(max_length=240, blank=True)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=OpportunitySourceStatus.choices, default=OpportunitySourceStatus.ACTIVE)
    discovered_at = models.DateTimeField(default=timezone.now)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="verified_opportunity_sources", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["opportunity"], condition=Q(is_primary=True, status=OpportunitySourceStatus.ACTIVE), name="opp_one_primary_active_source")]
        indexes = [models.Index(fields=["opportunity", "status"], name="opp_source_status_idx"), models.Index(fields=["is_primary", "status"], name="opp_source_primary_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = OpportunitySource.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de contrôle de source."})
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result


class OpportunitySourceCheckResult(models.TextChoices):
    UNCHANGED = "unchanged", "Inchangée"
    CHANGED = "changed", "Modifiée"
    UNREACHABLE = "unreachable", "Inaccessible"
    REMOVED = "removed", "Supprimée"


class OpportunitySourceCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(OpportunitySource, on_delete=models.PROTECT, related_name="checks")
    result = models.CharField(max_length=16, choices=OpportunitySourceCheckResult.choices)
    checked_at = models.DateTimeField(default=timezone.now)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="opportunity_source_checks", null=True, blank=True)
    fingerprint = models.CharField(max_length=128, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at", "-created_at", "id"]
        indexes = [models.Index(fields=["source", "checked_at"], name="opp_source_check_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("OpportunitySourceCheck est append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("OpportunitySourceCheck est append-only.")


class OpportunityRequirementKind(models.TextChoices):
    ELIGIBILITY = "eligibility", "Éligibilité"
    EDUCATION = "education", "Études"
    EXPERIENCE = "experience", "Expérience"
    DOCUMENT = "document", "Document"
    LANGUAGE = "language", "Langue"
    LOCATION = "location", "Localisation"
    AGE = "age", "Âge"
    FINANCIAL = "financial", "Financier"
    DEADLINE = "deadline", "Échéance"
    OTHER = "other", "Autre"


class OpportunityRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(OpportunityRevision, on_delete=models.CASCADE, related_name="requirements")
    kind = models.CharField(max_length=20, choices=OpportunityRequirementKind.choices)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["revision", "position", "created_at", "id"]
        indexes = [models.Index(fields=["revision", "position"], name="opp_req_revision_pos_idx"), models.Index(fields=["revision", "kind"], name="opp_req_revision_kind_idx")]

    def clean(self):
        super().clean()
        if self.revision_id and OpportunityRevision.objects.filter(pk=self.revision_id, published_at__isnull=False).exists():
            raise ValidationError({"revision": "Les Requirements d’une révision publiée sont immuables."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.revision.published_at is not None:
            raise ValidationError("Les Requirements d’une révision publiée sont immuables.")
        return super().delete(*args, **kwargs)


class OpportunitySave(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="opportunity_saves")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="saves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["profile", "opportunity"], name="opp_save_profile_unique")]
        indexes = [models.Index(fields=["profile", "created_at"], name="opp_save_profile_idx")]


class OpportunitySubmissionStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    UNDER_REVIEW = "under_review", "En revue"
    ACCEPTED = "accepted", "Acceptée"
    REJECTED = "rejected", "Rejetée"
    DUPLICATE = "duplicate", "Doublon"


class OpportunitySubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opportunity_submissions")
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=240, blank=True)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=OpportunitySubmissionStatus.choices, default=OpportunitySubmissionStatus.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="reviewed_opportunity_submissions", null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    resolved_opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="resolved_submissions", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [models.Index(fields=["status", "created_at"], name="opp_submission_status_idx")]

    def clean(self):
        super().clean()
        if self.status in {OpportunitySubmissionStatus.ACCEPTED, OpportunitySubmissionStatus.DUPLICATE} and not self.resolved_opportunity_id:
            raise ValidationError({"resolved_opportunity": "Cette décision doit référencer l’Opportunity canonique."})

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and not getattr(self, "_allow_status_transition", False):
            previous = OpportunitySubmission.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous is not None and previous != self.status:
                raise ValidationError({"status": "Utilisez le service de revue OpportunitySubmission."})
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_status_transition = False
        return result

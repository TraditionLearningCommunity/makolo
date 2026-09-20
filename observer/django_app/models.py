from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from observer.contracts import (
    ArtifactCompleteness,
    ArtifactOrigin,
    AttemptLifecycle,
    AttemptOutcome,
    AttemptStrategy,
    ObservationLifecycle,
    ObservationOutcome,
    ObservationTrigger,
)
from observer.identifiers import make_artifact_ref, make_attempt_ref, make_observation_ref

from .storage import private_observer_artifact_storage


OBSERVATION_TRIGGER_CHOICES = [(item.value, item.value) for item in ObservationTrigger]
OBSERVATION_LIFECYCLE_CHOICES = [(item.value, item.value) for item in ObservationLifecycle]
OBSERVATION_OUTCOME_CHOICES = [(item.value, item.value) for item in ObservationOutcome]
ATTEMPT_STRATEGY_CHOICES = [(item.value, item.value) for item in AttemptStrategy]
ATTEMPT_LIFECYCLE_CHOICES = [(item.value, item.value) for item in AttemptLifecycle]
ATTEMPT_OUTCOME_CHOICES = [(item.value, item.value) for item in AttemptOutcome]
ARTIFACT_ORIGIN_CHOICES = [(item.value, item.value) for item in ArtifactOrigin]
ARTIFACT_COMPLETENESS_CHOICES = [
    (item.value, item.value) for item in ArtifactCompleteness
]
SCOPE_KIND_CHOICES = [("host", "Host"), ("domain", "Domain")]


def observer_blob_upload_to(instance, filename):
    digest = (instance.content_digest or "").strip().lower()
    if len(digest) != 64:
        raise ValueError("ObserverBlob requires a SHA-256 digest before file storage")
    return f"sha256/{digest[:2]}/{digest[2:4]}/{digest}.bin"


class ObservationSeries(models.Model):
    target_key = models.CharField(max_length=96)
    kind = models.CharField(max_length=64)
    locator = models.TextField()
    profile_key = models.CharField(max_length=120)
    profile_fingerprint = models.CharField(max_length=128)
    watch_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    retry_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    http_etag = models.CharField(max_length=512, blank=True)
    http_last_modified = models.CharField(max_length=255, blank=True)
    validator_artifact_ref = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "observer_series"
        constraints = [
            models.UniqueConstraint(
                fields=["target_key", "profile_fingerprint"],
                name="obs_series_target_profile_uq",
            )
        ]
        indexes = [
            models.Index(fields=["watch_due_at", "id"], name="obs_series_watch_idx"),
            models.Index(fields=["retry_due_at", "id"], name="obs_series_retry_idx"),
        ]

    def __str__(self):
        return f"{self.target_key}:{self.profile_key}"


class ObserverHandoff(models.Model):
    handoff_key = models.CharField(max_length=96, unique=True)
    target_key = models.CharField(max_length=96)
    handoff_generation = models.PositiveBigIntegerField()
    locator = models.TextField()
    kind = models.CharField(max_length=64)
    requested_at = models.DateTimeField()
    contract_version = models.PositiveIntegerField(default=1)
    observation_hints = models.JSONField(default=dict, blank=True)
    absorbed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observer_handoff"
        constraints = [
            models.UniqueConstraint(
                fields=["target_key", "handoff_generation"],
                name="obs_handoff_target_gen_uq",
            ),
            models.CheckConstraint(
                condition=Q(handoff_generation__gte=1),
                name="obs_handoff_gen_gte_1",
            ),
        ]
    def __str__(self):
        return self.handoff_key


class Observation(models.Model):
    observation_ref = models.CharField(
        max_length=255,
        unique=True,
        default=make_observation_ref,
        editable=False,
    )
    series = models.ForeignKey(
        ObservationSeries,
        on_delete=models.PROTECT,
        related_name="observations",
    )
    source_handoff = models.ForeignKey(
        ObserverHandoff,
        on_delete=models.PROTECT,
        related_name="observations",
    )
    trigger = models.CharField(max_length=16, choices=OBSERVATION_TRIGGER_CHOICES)
    lifecycle = models.CharField(
        max_length=16,
        choices=OBSERVATION_LIFECYCLE_CHOICES,
        default=ObservationLifecycle.OPEN.value,
    )
    outcome = models.CharField(
        max_length=16,
        choices=OBSERVATION_OUTCOME_CHOICES,
        blank=True,
    )
    started_at = models.DateTimeField()
    observed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_locator = models.TextField()
    final_locator = models.TextField(blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    retry_at = models.DateTimeField(null=True, blank=True)
    profile_ref = models.CharField(max_length=120)
    profile_fingerprint = models.CharField(max_length=128)
    policy_fingerprint = models.CharField(max_length=128)
    claim_token = models.UUIDField(null=True, blank=True, db_index=True)
    claimed_by = models.CharField(max_length=120, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    prospector_reported_at = models.DateTimeField(null=True, blank=True)
    revalidated_artifacts = models.ManyToManyField(
        "ObservedArtifact",
        related_name="revalidated_by_observations",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "observer_observation"
        ordering = ["started_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["series"],
                condition=Q(lifecycle=ObservationLifecycle.OPEN.value),
                name="obs_one_open_series_uq",
            ),
            models.CheckConstraint(
                condition=Q(response_status__isnull=True)
                | Q(response_status__gte=100, response_status__lte=599),
                name="obs_response_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(lifecycle=ObservationLifecycle.OPEN.value)
                    | (
                        Q(
                            claim_token__isnull=False,
                            lease_expires_at__isnull=False,
                        )
                        & ~Q(claimed_by="")
                    )
                ),
                name="obs_open_requires_claim",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        lifecycle=ObservationLifecycle.OPEN.value,
                        outcome="",
                        observed_at__isnull=True,
                        completed_at__isnull=True,
                        failure_code="",
                        retry_at__isnull=True,
                    )
                    | (
                        Q(
                            lifecycle=ObservationLifecycle.FINALIZED.value,
                            observed_at__isnull=False,
                            completed_at__isnull=False,
                        )
                        & ~Q(outcome="")
                    )
                ),
                name="obs_lifecycle_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(outcome=ObservationOutcome.FAILED.value) & ~Q(failure_code="")
                )
                | Q(
                    outcome__in=[
                        ObservationOutcome.OBSERVED.value,
                        ObservationOutcome.NOT_MODIFIED.value,
                    ],
                    failure_code="",
                    retry_at__isnull=True,
                )
                | Q(outcome=""),
                name="obs_outcome_failure_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["lifecycle", "lease_expires_at", "id"],
                name="obs_observation_lease_idx",
            ),
            models.Index(
                fields=["series", "completed_at", "id"],
                name="obs_observation_history_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.source_handoff_id and self.series_id:
            if self.source_handoff.target_key != self.series.target_key:
                errors["source_handoff"] = (
                    "Le handoff source doit viser la même cible que la série."
                )
            if (
                self.source_handoff.kind != self.series.kind
                or self.source_handoff.locator != self.series.locator
            ):
                errors["source_handoff"] = (
                    "Le handoff source doit conserver kind/locator de la série."
                )
        if self.series_id:
            if self.profile_fingerprint != self.series.profile_fingerprint:
                errors["profile_fingerprint"] = (
                    "Le fingerprint doit photographier celui de la série."
                )
            if self.requested_locator != self.series.locator:
                errors["requested_locator"] = (
                    "L'Observation doit partir du locator de sa série."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.observation_ref


class ObservationAttempt(models.Model):
    attempt_ref = models.CharField(
        max_length=255,
        unique=True,
        default=make_attempt_ref,
        editable=False,
    )
    observation = models.ForeignKey(
        Observation,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    ordinal = models.PositiveIntegerField()
    strategy = models.CharField(max_length=32, choices=ATTEMPT_STRATEGY_CHOICES)
    lifecycle = models.CharField(
        max_length=16,
        choices=ATTEMPT_LIFECYCLE_CHOICES,
        default=AttemptLifecycle.OPEN.value,
    )
    outcome = models.CharField(
        max_length=16,
        choices=ATTEMPT_OUTCOME_CHOICES,
        blank=True,
    )
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_locator = models.TextField()
    final_locator = models.TextField(blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    retry_after_at = models.DateTimeField(null=True, blank=True)
    redirect_count = models.PositiveIntegerField(default=0)
    wire_bytes = models.PositiveBigIntegerField(default=0)
    decoded_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observer_attempt"
        ordering = ["observation", "ordinal"]
        constraints = [
            models.UniqueConstraint(
                fields=["observation", "ordinal"],
                name="obs_attempt_ordinal_uq",
            ),
            models.CheckConstraint(
                condition=Q(ordinal__gte=1),
                name="obs_attempt_ordinal_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(response_status__isnull=True)
                | Q(response_status__gte=100, response_status__lte=599),
                name="obs_attempt_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        lifecycle=AttemptLifecycle.OPEN.value,
                        outcome="",
                        completed_at__isnull=True,
                        failure_code="",
                    )
                    | (
                        Q(
                            lifecycle=AttemptLifecycle.FINALIZED.value,
                            completed_at__isnull=False,
                        )
                        & ~Q(outcome="")
                    )
                ),
                name="obs_attempt_lifecycle_consist",
            ),
            models.CheckConstraint(
                condition=(
                    Q(outcome=AttemptOutcome.FAILED.value) & ~Q(failure_code="")
                )
                | ~Q(outcome=AttemptOutcome.FAILED.value),
                name="obs_attempt_failure_consist",
            ),
        ]

    def __str__(self):
        return self.attempt_ref


class ObserverBlob(models.Model):
    content_digest = models.CharField(max_length=64, unique=True)
    byte_length = models.PositiveBigIntegerField()
    file = models.FileField(
        storage=private_observer_artifact_storage,
        upload_to=observer_blob_upload_to,
        max_length=500,
        blank=True,
    )
    purged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observer_blob"
        constraints = [
            models.CheckConstraint(
                condition=Q(byte_length__gte=0),
                name="obs_blob_size_gte_0",
            )
        ]

    def clean(self):
        super().clean()
        digest = (self.content_digest or "").strip().lower()
        if len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise ValidationError(
                {"content_digest": "SHA-256 hex digest invalide."}
            )
        self.content_digest = digest
        if self.purged_at is None and not self.file:
            raise ValidationError(
                {"file": "Un blob actif exige un fichier privé."}
            )
        if self.purged_at is not None and self.file:
            raise ValidationError(
                {
                    "file": (
                        "Un blob marqué purgé ne doit plus référencer "
                        "de fichier actif."
                    )
                }
            )

    def __str__(self):
        return self.content_digest


class ObservedArtifact(models.Model):
    artifact_ref = models.CharField(
        max_length=255,
        unique=True,
        default=make_artifact_ref,
        editable=False,
    )
    observation = models.ForeignKey(
        Observation,
        on_delete=models.PROTECT,
        related_name="artifacts",
    )
    producing_attempt = models.ForeignKey(
        ObservationAttempt,
        on_delete=models.PROTECT,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    blob = models.ForeignKey(
        ObserverBlob,
        on_delete=models.PROTECT,
        related_name="artifacts",
    )
    role = models.CharField(max_length=64)
    origin = models.CharField(max_length=16, choices=ARTIFACT_ORIGIN_CHOICES)
    completeness = models.CharField(
        max_length=16,
        choices=ARTIFACT_COMPLETENESS_CHOICES,
    )
    declared_media_type = models.CharField(max_length=180, blank=True)
    detected_media_type = models.CharField(max_length=180, blank=True)
    charset = models.CharField(max_length=80, blank=True)
    captured_at = models.DateTimeField()
    source_artifact = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="derived_artifacts",
        null=True,
        blank=True,
    )
    transformation_name = models.CharField(max_length=120, blank=True)
    transformation_version = models.CharField(max_length=120, blank=True)
    transformation_fingerprint = models.CharField(max_length=128, blank=True)
    protection_context_ref = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observer_artifact"
        ordering = ["captured_at", "id"]
        indexes = [
            models.Index(
                fields=["observation", "captured_at", "id"],
                name="obs_artifact_observation_idx",
            ),
            models.Index(fields=["blob", "id"], name="obs_artifact_blob_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.producing_attempt_id
            and self.producing_attempt.observation_id != self.observation_id
        ):
            errors["producing_attempt"] = (
                "L'Attempt doit appartenir à la même Observation."
            )
        is_derived = self.origin == ArtifactOrigin.DERIVED.value
        has_transform = bool(
            (self.transformation_name or "").strip()
            and (
                (self.transformation_version or "").strip()
                or (self.transformation_fingerprint or "").strip()
            )
        )
        if is_derived:
            if not self.source_artifact_id:
                errors["source_artifact"] = (
                    "Un artefact dérivé exige une source."
                )
            elif self.source_artifact.observation_id != self.observation_id:
                errors["source_artifact"] = (
                    "La source doit appartenir à la même Observation."
                )
            if not has_transform:
                errors["transformation_name"] = (
                    "Un artefact dérivé exige une transformation versionnée."
                )
        elif (
            self.source_artifact_id
            or self.transformation_name
            or self.transformation_version
            or self.transformation_fingerprint
        ):
            errors["origin"] = (
                "Seuls les artefacts dérivés portent une provenance "
                "de transformation."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.artifact_ref


class ObservedReference(models.Model):
    observation = models.ForeignKey(
        Observation,
        on_delete=models.CASCADE,
        related_name="observed_references",
    )
    attempt = models.ForeignKey(
        ObservationAttempt,
        on_delete=models.SET_NULL,
        related_name="observed_references",
        null=True,
        blank=True,
    )
    reference_key = models.CharField(max_length=64)
    relation = models.CharField(max_length=80)
    locator = models.TextField()
    kind = models.CharField(max_length=64, default="web_url")
    discovered_at = models.DateTimeField()
    attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observer_reference"
        ordering = ["discovered_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["observation", "reference_key"],
                name="obs_reference_key_uq",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.attempt_id
            and self.attempt.observation_id != self.observation_id
        ):
            raise ValidationError(
                {
                    "attempt": (
                        "L'Attempt doit appartenir à la même Observation."
                    )
                }
            )

    def __str__(self):
        return f"{self.relation}:{self.locator}"


class ObserverScopeState(models.Model):
    scope_kind = models.CharField(max_length=16, choices=SCOPE_KIND_CHOICES)
    scope_key = models.CharField(max_length=255)
    not_before = models.DateTimeField(null=True, blank=True, db_index=True)
    last_request_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "observer_scope_state"
        constraints = [
            models.UniqueConstraint(
                fields=["scope_kind", "scope_key"],
                name="obs_scope_state_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["scope_kind", "not_before", "id"],
                name="obs_scope_due_idx",
            )
        ]

    def __str__(self):
        return f"{self.scope_kind}:{self.scope_key}"

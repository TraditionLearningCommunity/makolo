import django.db.models.deletion
from django.db import migrations, models

import observer.django_app.models
import observer.django_app.storage
import observer.identifiers


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ObservationSeries",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("target_key", models.CharField(max_length=96)),
                ("kind", models.CharField(max_length=64)),
                ("locator", models.TextField()),
                ("profile_key", models.CharField(max_length=120)),
                ("profile_fingerprint", models.CharField(max_length=128)),
                (
                    "watch_due_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "retry_due_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("http_etag", models.CharField(blank=True, max_length=512)),
                (
                    "http_last_modified",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "validator_artifact_ref",
                    models.CharField(blank=True, max_length=255),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "observer_series",
                "indexes": [
                    models.Index(
                        fields=["watch_due_at", "id"],
                        name="obs_series_watch_idx",
                    ),
                    models.Index(
                        fields=["retry_due_at", "id"],
                        name="obs_series_retry_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("target_key", "profile_fingerprint"),
                        name="obs_series_target_profile_uq",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ObserverHandoff",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("handoff_key", models.CharField(max_length=96, unique=True)),
                ("target_key", models.CharField(max_length=96)),
                ("handoff_generation", models.PositiveBigIntegerField()),
                ("locator", models.TextField()),
                ("kind", models.CharField(max_length=64)),
                ("requested_at", models.DateTimeField()),
                ("contract_version", models.PositiveIntegerField(default=1)),
                (
                    "observation_hints",
                    models.JSONField(blank=True, default=dict),
                ),
                ("absorbed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "observer_handoff",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("target_key", "handoff_generation"),
                        name="obs_handoff_target_gen_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(handoff_generation__gte=1),
                        name="obs_handoff_gen_gte_1",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Observation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "observation_ref",
                    models.CharField(
                        default=observer.identifiers.make_observation_ref,
                        editable=False,
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "trigger",
                    models.CharField(
                        choices=[
                            ("handoff", "handoff"),
                            ("retry", "retry"),
                            ("watch", "watch"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "lifecycle",
                    models.CharField(
                        choices=[("open", "open"), ("finalized", "finalized")],
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("observed", "observed"),
                            ("not_modified", "not_modified"),
                            ("failed", "failed"),
                        ],
                        max_length=16,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("requested_locator", models.TextField()),
                ("final_locator", models.TextField(blank=True)),
                (
                    "response_status",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("failure_code", models.CharField(blank=True, max_length=120)),
                ("retry_at", models.DateTimeField(blank=True, null=True)),
                ("profile_ref", models.CharField(max_length=120)),
                ("profile_fingerprint", models.CharField(max_length=128)),
                ("policy_fingerprint", models.CharField(max_length=128)),
                (
                    "claim_token",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
                ("claimed_by", models.CharField(blank=True, max_length=120)),
                (
                    "lease_expires_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "prospector_reported_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "series",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="observations",
                        to="observer_storage.observationseries",
                    ),
                ),
                (
                    "source_handoff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="observations",
                        to="observer_storage.observerhandoff",
                    ),
                ),
            ],
            options={
                "db_table": "observer_observation",
                "ordering": ["started_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["lifecycle", "lease_expires_at", "id"],
                        name="obs_observation_lease_idx",
                    ),
                    models.Index(
                        fields=["series", "completed_at", "id"],
                        name="obs_observation_history_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(lifecycle="open"),
                        fields=("series",),
                        name="obs_one_open_series_uq",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(response_status__isnull=True)
                            | models.Q(
                                response_status__gte=100,
                                response_status__lte=599,
                            )
                        ),
                        name="obs_response_status_valid",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                lifecycle="open",
                                outcome="",
                                observed_at__isnull=True,
                                completed_at__isnull=True,
                                failure_code="",
                                retry_at__isnull=True,
                            )
                            | (
                                models.Q(
                                    lifecycle="finalized",
                                    observed_at__isnull=False,
                                    completed_at__isnull=False,
                                )
                                & ~models.Q(outcome="")
                            )
                        ),
                        name="obs_lifecycle_consistent",
                    ),
                    models.CheckConstraint(
                        condition=(
                            (
                                models.Q(outcome="failed")
                                & ~models.Q(failure_code="")
                            )
                            | models.Q(
                                outcome__in=["observed", "not_modified"],
                                failure_code="",
                                retry_at__isnull=True,
                            )
                            | models.Q(outcome="")
                        ),
                        name="obs_outcome_failure_consistent",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ObservationAttempt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "attempt_ref",
                    models.CharField(
                        default=observer.identifiers.make_attempt_ref,
                        editable=False,
                        max_length=255,
                        unique=True,
                    ),
                ),
                ("ordinal", models.PositiveIntegerField()),
                (
                    "strategy",
                    models.CharField(
                        choices=[
                            ("direct_http", "direct_http"),
                            ("browser_render", "browser_render"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "lifecycle",
                    models.CharField(
                        choices=[("open", "open"), ("finalized", "finalized")],
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("succeeded", "succeeded"),
                            ("failed", "failed"),
                            ("interrupted", "interrupted"),
                            ("unknown", "unknown"),
                        ],
                        max_length=16,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("requested_locator", models.TextField()),
                ("final_locator", models.TextField(blank=True)),
                (
                    "response_status",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("failure_code", models.CharField(blank=True, max_length=120)),
                (
                    "retry_after_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("redirect_count", models.PositiveIntegerField(default=0)),
                ("wire_bytes", models.PositiveBigIntegerField(default=0)),
                ("decoded_bytes", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="observer_storage.observation",
                    ),
                ),
            ],
            options={
                "db_table": "observer_attempt",
                "ordering": ["observation", "ordinal"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("observation", "ordinal"),
                        name="obs_attempt_ordinal_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(ordinal__gte=1),
                        name="obs_attempt_ordinal_gte_1",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(response_status__isnull=True)
                            | models.Q(
                                response_status__gte=100,
                                response_status__lte=599,
                            )
                        ),
                        name="obs_attempt_status_valid",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                lifecycle="open",
                                outcome="",
                                completed_at__isnull=True,
                                failure_code="",
                            )
                            | (
                                models.Q(
                                    lifecycle="finalized",
                                    completed_at__isnull=False,
                                )
                                & ~models.Q(outcome="")
                            )
                        ),
                        name="obs_attempt_lifecycle_consist",
                    ),
                    models.CheckConstraint(
                        condition=(
                            (
                                models.Q(outcome="failed")
                                & ~models.Q(failure_code="")
                            )
                            | ~models.Q(outcome="failed")
                        ),
                        name="obs_attempt_failure_consist",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ObserverBlob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("content_digest", models.CharField(max_length=64, unique=True)),
                ("byte_length", models.PositiveBigIntegerField()),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        max_length=500,
                        storage=observer.django_app.storage.PrivateObserverArtifactStorage(),
                        upload_to=observer.django_app.models.observer_blob_upload_to,
                    ),
                ),
                ("purged_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "observer_blob",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(byte_length__gte=0),
                        name="obs_blob_size_gte_0",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ObservedArtifact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "artifact_ref",
                    models.CharField(
                        default=observer.identifiers.make_artifact_ref,
                        editable=False,
                        max_length=255,
                        unique=True,
                    ),
                ),
                ("role", models.CharField(max_length=64)),
                (
                    "origin",
                    models.CharField(
                        choices=[
                            ("captured", "captured"),
                            ("rendered", "rendered"),
                            ("derived", "derived"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "completeness",
                    models.CharField(
                        choices=[
                            ("complete", "complete"),
                            ("truncated", "truncated"),
                            ("incomplete", "incomplete"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "declared_media_type",
                    models.CharField(blank=True, max_length=180),
                ),
                (
                    "detected_media_type",
                    models.CharField(blank=True, max_length=180),
                ),
                ("charset", models.CharField(blank=True, max_length=80)),
                ("captured_at", models.DateTimeField()),
                (
                    "transformation_name",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "transformation_version",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "transformation_fingerprint",
                    models.CharField(blank=True, max_length=128),
                ),
                (
                    "protection_context_ref",
                    models.CharField(blank=True, max_length=255),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "blob",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="artifacts",
                        to="observer_storage.observerblob",
                    ),
                ),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="artifacts",
                        to="observer_storage.observation",
                    ),
                ),
                (
                    "producing_attempt",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="artifacts",
                        to="observer_storage.observationattempt",
                    ),
                ),
                (
                    "source_artifact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="derived_artifacts",
                        to="observer_storage.observedartifact",
                    ),
                ),
            ],
            options={
                "db_table": "observer_artifact",
                "ordering": ["captured_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["observation", "captured_at", "id"],
                        name="obs_artifact_observation_idx",
                    ),
                    models.Index(
                        fields=["blob", "id"],
                        name="obs_artifact_blob_idx",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="observation",
            name="revalidated_artifacts",
            field=models.ManyToManyField(
                blank=True,
                related_name="revalidated_by_observations",
                to="observer_storage.observedartifact",
            ),
        ),
        migrations.CreateModel(
            name="ObservedReference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reference_key", models.CharField(max_length=64)),
                ("relation", models.CharField(max_length=80)),
                ("locator", models.TextField()),
                ("kind", models.CharField(default="web_url", max_length=64)),
                ("discovered_at", models.DateTimeField()),
                ("attributes", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "attempt",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="observed_references",
                        to="observer_storage.observationattempt",
                    ),
                ),
                (
                    "observation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observed_references",
                        to="observer_storage.observation",
                    ),
                ),
            ],
            options={
                "db_table": "observer_reference",
                "ordering": ["discovered_at", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("observation", "reference_key"),
                        name="obs_reference_key_uq",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ObserverScopeState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "scope_kind",
                    models.CharField(
                        choices=[("host", "Host"), ("domain", "Domain")],
                        max_length=16,
                    ),
                ),
                ("scope_key", models.CharField(max_length=255)),
                (
                    "not_before",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "last_request_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "observer_scope_state",
                "indexes": [
                    models.Index(
                        fields=["scope_kind", "not_before", "id"],
                        name="obs_scope_due_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("scope_kind", "scope_key"),
                        name="obs_scope_state_uq",
                    ),
                ],
            },
        ),
    ]

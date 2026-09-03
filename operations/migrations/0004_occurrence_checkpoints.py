import uuid

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("access", "0003_external_beneficiary"),
        ("journeys", "0002_external_beneficiary"),
        ("operations", "0003_occurrence_placement"),
    ]

    operations = [
        migrations.CreateModel(
            name="OccurrenceCheckpoint",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=180)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("position", models.PositiveIntegerField(default=0)),
                ("required", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("planned", "Planifié"), ("open", "Ouvert"), ("paused", "En pause"), ("closed", "Fermé")], default="planned", max_length=16)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("occurrence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checkpoints", to="activities.occurrence")),
            ],
            options={"ordering": ["occurrence_id", "position", "label", "id"]},
        ),
        migrations.CreateModel(
            name="CheckpointAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_assignments_made", to=settings.AUTH_USER_MODEL)),
                ("checkpoint", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assignments", to="operations.occurrencecheckpoint")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-assigned_at", "id"]},
        ),
        migrations.CreateModel(
            name="CheckpointObservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("observed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("client_reference", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("access_use", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_observations", to="access.accessuse")),
                ("checkpoint", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="observations", to="operations.occurrencecheckpoint")),
                ("external_beneficiary", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_observations", to="journeys.externalbeneficiary")),
                ("observed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_observations_made", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="checkpoint_observations_as_beneficiary", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-observed_at", "id"]},
        ),
        migrations.AddConstraint(model_name="occurrencecheckpoint", constraint=models.UniqueConstraint(fields=("occurrence", "key"), name="ops_checkpoint_key_uq")),
        migrations.AddIndex(model_name="occurrencecheckpoint", index=models.Index(fields=["occurrence", "active", "position"], name="ops_checkpoint_occ_idx")),
        migrations.AddConstraint(model_name="checkpointassignment", constraint=models.UniqueConstraint(condition=Q(ended_at__isnull=True), fields=("checkpoint", "profile"), name="ops_checkpoint_active_asg_uq")),
        migrations.AddConstraint(model_name="checkpointassignment", constraint=models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F("assigned_at")), name="ops_checkpoint_asg_time_ck")),
        migrations.AddIndex(model_name="checkpointassignment", index=models.Index(fields=["checkpoint", "ended_at"], name="ops_checkpoint_asg_idx")),
        migrations.AddIndex(model_name="checkpointassignment", index=models.Index(fields=["profile", "ended_at"], name="ops_checkpoint_prof_idx")),
        migrations.AddConstraint(model_name="checkpointobservation", constraint=models.CheckConstraint(condition=(Q(profile__isnull=False) & Q(external_beneficiary__isnull=True)) | (Q(profile__isnull=True) & Q(external_beneficiary__isnull=False)), name="ops_checkpoint_obs_subject_ck")),
        migrations.AddConstraint(model_name="checkpointobservation", constraint=models.UniqueConstraint(condition=Q(profile__isnull=False), fields=("checkpoint", "profile"), name="ops_checkpoint_obs_profile_uq")),
        migrations.AddConstraint(model_name="checkpointobservation", constraint=models.UniqueConstraint(condition=Q(external_beneficiary__isnull=False), fields=("checkpoint", "external_beneficiary"), name="ops_checkpoint_obs_ext_uq")),
        migrations.AddConstraint(model_name="checkpointobservation", constraint=models.UniqueConstraint(condition=~Q(source="") & ~Q(client_reference=""), fields=("source", "client_reference"), name="ops_checkpoint_obs_client_uq")),
        migrations.AddIndex(model_name="checkpointobservation", index=models.Index(fields=["checkpoint", "observed_at"], name="ops_checkpoint_obs_idx")),
        migrations.AddIndex(model_name="checkpointobservation", index=models.Index(fields=["profile", "observed_at"], name="ops_checkpoint_obs_prof_idx")),
        migrations.AddIndex(model_name="checkpointobservation", index=models.Index(fields=["external_beneficiary", "observed_at"], name="ops_checkpoint_obs_ext_idx")),
        migrations.AddIndex(model_name="checkpointobservation", index=models.Index(fields=["access_use"], name="ops_checkpoint_obs_access_idx")),
    ]

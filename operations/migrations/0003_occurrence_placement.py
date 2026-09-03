import uuid

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0002_occurrence_place"),
        ("journeys", "0002_external_beneficiary"),
        ("operations", "0002_canonical_incident_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlacementPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=180)),
                ("required", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "occurrence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="placement_plans",
                        to="activities.occurrence",
                    ),
                ),
            ],
            options={"ordering": ["occurrence_id", "label", "id"]},
        ),
        migrations.CreateModel(
            name="PlacementUnit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=180)),
                ("kind", models.CharField(blank=True, max_length=48)),
                ("position", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                (
                    "exclusive",
                    models.BooleanField(
                        default=False,
                        help_text="Politique d’exclusivité du placement; ne représente pas une capacité.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="operations.placementunit",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="units",
                        to="operations.placementplan",
                    ),
                ),
            ],
            options={"ordering": ["plan_id", "position", "label", "id"]},
        ),
        migrations.CreateModel(
            name="PlacementAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placement_assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "external_beneficiary",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placement_assignments",
                        to="journeys.externalbeneficiary",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="operations.placementplan",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placement_assignments_as_beneficiary",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="operations.placementunit",
                    ),
                ),
            ],
            options={"ordering": ["-assigned_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="placementplan",
            constraint=models.UniqueConstraint(fields=("occurrence", "key"), name="ops_place_plan_key_uq"),
        ),
        migrations.AddIndex(
            model_name="placementplan",
            index=models.Index(fields=["occurrence", "active"], name="ops_place_plan_occ_idx"),
        ),
        migrations.AddConstraint(
            model_name="placementunit",
            constraint=models.UniqueConstraint(fields=("plan", "key"), name="ops_place_unit_key_uq"),
        ),
        migrations.AddIndex(
            model_name="placementunit",
            index=models.Index(fields=["plan", "active", "position"], name="ops_place_unit_plan_idx"),
        ),
        migrations.AddConstraint(
            model_name="placementassignment",
            constraint=models.CheckConstraint(
                condition=(models.Q(external_beneficiary__isnull=True, profile__isnull=False) | models.Q(external_beneficiary__isnull=False, profile__isnull=True)),
                name="ops_place_one_subject_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="placementassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(ended_at__isnull=True, profile__isnull=False),
                fields=("plan", "profile"),
                name="ops_place_active_profile_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="placementassignment",
            constraint=models.UniqueConstraint(
                condition=models.Q(ended_at__isnull=True, external_beneficiary__isnull=False),
                fields=("plan", "external_beneficiary"),
                name="ops_place_active_ext_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="placementassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F("assigned_at")),
                name="ops_place_end_after_start_ck",
            ),
        ),
        migrations.AddIndex(
            model_name="placementassignment",
            index=models.Index(fields=["plan", "ended_at"], name="ops_place_asg_plan_idx"),
        ),
        migrations.AddIndex(
            model_name="placementassignment",
            index=models.Index(fields=["unit", "ended_at"], name="ops_place_asg_unit_idx"),
        ),
        migrations.AddIndex(
            model_name="placementassignment",
            index=models.Index(fields=["profile", "assigned_at"], name="ops_place_asg_profile_idx"),
        ),
        migrations.AddIndex(
            model_name="placementassignment",
            index=models.Index(fields=["external_beneficiary", "assigned_at"], name="ops_place_asg_ext_idx"),
        ),
    ]

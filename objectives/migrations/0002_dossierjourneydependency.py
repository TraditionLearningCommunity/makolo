# Generated manually for D2; additive migration only.
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):

    dependencies = [
        ("objectives", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DossierJourneyDependency",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "state",
                    models.CharField(
                        choices=[("active", "Active"), ("waived", "Levée"), ("removed", "Retirée")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("waiver_reason", models.CharField(blank=True, max_length=280)),
                (
                    "closed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dossier_journey_dependencies_closed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dossier_journey_dependencies_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dependent_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dependencies_as_dependent",
                        to="objectives.dossierjourneylink",
                    ),
                ),
                (
                    "dossier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="journey_dependencies",
                        to="objectives.dossier",
                    ),
                ),
                (
                    "required_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dependencies_as_required",
                        to="objectives.dossierjourneylink",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="dossierjourneydependency",
            constraint=models.CheckConstraint(
                condition=~Q(dependent_link=F("required_link")),
                name="dossier_dependency_distinct_links",
            ),
        ),
        migrations.AddConstraint(
            model_name="dossierjourneydependency",
            constraint=models.UniqueConstraint(
                condition=Q(state="active"),
                fields=("dossier", "dependent_link", "required_link"),
                name="dossier_dependency_one_active_pair",
            ),
        ),
        migrations.AddIndex(
            model_name="dossierjourneydependency",
            index=models.Index(fields=["dossier", "state"], name="dossier_dependency_state_idx"),
        ),
        migrations.AddIndex(
            model_name="dossierjourneydependency",
            index=models.Index(fields=["dependent_link", "state"], name="dossier_dep_dependent_idx"),
        ),
        migrations.AddIndex(
            model_name="dossierjourneydependency",
            index=models.Index(fields=["required_link", "state"], name="dossier_dep_required_idx"),
        ),
    ]

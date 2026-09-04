import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0004_event_policy_ordering"),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("opportunities", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProactivePreparationCursor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("watch_kind", models.CharField(choices=[("opportunity", "Opportunity suivie"), ("journey", "Démarche")], max_length=20)),
                ("projection_signature", models.CharField(max_length=96)),
                ("notification_signature", models.CharField(max_length=96)),
                ("signature_version", models.CharField(max_length=40)),
                ("transition_sequence", models.PositiveBigIntegerField(default=0)),
                ("last_evaluated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_notified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "journey",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proactive_preparation_cursors",
                        to="journeys.journey",
                    ),
                ),
                (
                    "opportunity_save",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proactive_preparation_cursors",
                        to="opportunities.opportunitysave",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proactive_preparation_cursors",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["last_evaluated_at", "id"],
                "indexes": [
                    models.Index(fields=["last_evaluated_at", "id"], name="auto_prep_cursor_eval_idx"),
                    models.Index(fields=["recipient", "watch_kind"], name="auto_prep_cursor_rec_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(("journey__isnull", True), ("opportunity_save__isnull", False), ("watch_kind", "opportunity"))
                            | models.Q(("journey__isnull", False), ("opportunity_save__isnull", True), ("watch_kind", "journey"))
                        ),
                        name="auto_prep_cursor_anchor_ck",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("opportunity_save__isnull", False)),
                        fields=("recipient", "opportunity_save"),
                        name="auto_prep_cursor_opp_unique",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("journey__isnull", False)),
                        fields=("recipient", "journey"),
                        name="auto_prep_cursor_journey_unique",
                    ),
                ],
            },
        ),
    ]

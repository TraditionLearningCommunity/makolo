import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("events", "0002_event_organization"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventAutomationPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_active", models.BooleanField(default=True)),
                ("reminder_7d_enabled", models.BooleanField(default=False)),
                ("reminder_24h_enabled", models.BooleanField(default=True)),
                ("reminder_2h_enabled", models.BooleanField(default=True)),
                ("post_event_followup_enabled", models.BooleanField(default=True)),
                ("auto_complete_event", models.BooleanField(default=True)),
                ("auto_close_sales_at_start", models.BooleanField(default=True)),
                ("capacity_alerts_enabled", models.BooleanField(default=True)),
                ("capacity_alert_percent", models.PositiveSmallIntegerField(default=80, validators=[MinValueValidator(1), MaxValueValidator(100)])),
                ("low_stock_alerts_enabled", models.BooleanField(default=True)),
                ("low_stock_threshold", models.PositiveIntegerField(default=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="automation_policy", to="events.event")),
            ],
            options={"ordering": ["event__start_at"]},
        ),
        migrations.CreateModel(
            name="AutomationRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("rule_key", models.CharField(max_length=80)),
                ("dedup_key", models.CharField(max_length=255, unique=True)),
                ("status", models.CharField(choices=[("success", "Réussi"), ("failed", "Échoué"), ("skipped", "Ignoré")], default="success", max_length=16)),
                ("summary", models.CharField(blank=True, max_length=255)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="automation_runs", to="events.event")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="automationrun",
            index=models.Index(fields=["rule_key", "created_at"], name="automation_rule_ke_bdd6bd_idx"),
        ),
        migrations.AddIndex(
            model_name="automationrun",
            index=models.Index(fields=["event", "created_at"], name="automation_event_i_a43472_idx"),
        ),
    ]

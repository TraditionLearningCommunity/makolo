import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0002_crm_workflow_engine"),
        ("core", "0001_domain_events"),
        ("activities", "0002_occurrence_place"),
        ("organizations", "0003_team_teammembership"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("trigger_event_type", models.CharField(max_length=100)),
                ("conditions", models.JSONField(blank=True, default=dict)),
                ("action_kind", models.CharField(choices=[("notification", "Créer une notification")], default="notification", max_length=32)),
                ("action_config", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="automation_rules", to="activities.activity")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_domain_automation_rules", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="domain_automation_rules", to="organizations.organization")),
            ],
            options={"ordering": ["space_id", "name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="automationrule",
            constraint=models.UniqueConstraint(fields=("space", "name"), name="auto_domain_rule_space_name_unique"),
        ),
        migrations.AddIndex(
            model_name="automationrule",
            index=models.Index(fields=["space", "is_active", "trigger_event_type"], name="auto_de_rule_space_idx"),
        ),
        migrations.AddIndex(
            model_name="automationrule",
            index=models.Index(fields=["activity", "is_active", "trigger_event_type"], name="auto_de_rule_activity_idx"),
        ),
        migrations.CreateModel(
            name="AutomationExecution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(choices=[("notification", "Créer une notification")], max_length=32)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("running", "En cours"), ("completed", "Terminé"), ("skipped", "Ignoré"), ("failed", "Échoué")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("domain_event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="automation_executions", to="core.domaineventoutbox")),
                ("rule", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="automation.automationrule")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="automationexecution",
            constraint=models.UniqueConstraint(fields=("rule", "domain_event"), name="auto_execution_rule_event_unique"),
        ),
        migrations.AddConstraint(
            model_name="automationexecution",
            constraint=models.CheckConstraint(condition=models.Q(("max_attempts__gt", 0)), name="auto_execution_max_attempts_pos"),
        ),
        migrations.AddIndex(
            model_name="automationexecution",
            index=models.Index(fields=["rule", "status"], name="auto_de_exec_rule_status_idx"),
        ),
        migrations.AddIndex(
            model_name="automationexecution",
            index=models.Index(fields=["domain_event"], name="auto_de_exec_event_idx"),
        ),
        migrations.AddIndex(
            model_name="automationexecution",
            index=models.Index(fields=["created_at"], name="auto_de_exec_created_idx"),
        ),
    ]

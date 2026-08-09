import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0002_organizationfollow"),
        ("events", "0002_event_organization"),
        ("payments", "0001_initial"),
        ("scanner", "0002_eventaccessgate_smart_access"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkerHeartbeat",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("worker_name", models.CharField(max_length=80)),
                ("instance_id", models.CharField(default="default", max_length=120)),
                ("state", models.CharField(choices=[("healthy", "Opérationnel"), ("degraded", "Dégradé"), ("stopped", "Arrêté")], default="healthy", max_length=16)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_cycle_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_cycle_finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["worker_name", "instance_id"]},
        ),
        migrations.CreateModel(
            name="OperationsAuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(max_length=80)),
                ("target_type", models.CharField(max_length=40)),
                ("target_id", models.CharField(max_length=64)),
                ("summary", models.CharField(max_length=255)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_audit_actions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OperationsIncident",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("category", models.CharField(choices=[("organization", "Organisation"), ("event", "Événement"), ("payment", "Paiement"), ("access", "Accès / Scan"), ("automation", "Autopilot / Automation"), ("notification", "Notification"), ("security", "Sécurité"), ("support", "Support"), ("other", "Autre")], max_length=24)),
                ("severity", models.CharField(choices=[("low", "Faible"), ("medium", "Moyenne"), ("high", "Élevée"), ("critical", "Critique")], default="medium", max_length=16)),
                ("status", models.CharField(choices=[("open", "Ouvert"), ("investigating", "En investigation"), ("monitoring", "Sous surveillance"), ("resolved", "Résolu"), ("dismissed", "Classé sans suite")], default="open", max_length=20)),
                ("description", models.TextField()),
                ("resolution", models.TextField(blank=True)),
                ("detected_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_incidents_assigned", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_incidents", to="events.event")),
                ("opened_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operations_incidents_opened", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_incidents", to="organizations.organization")),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_incidents", to="payments.payment")),
                ("scan_log", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="operations_incidents", to="scanner.scanlog")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ModerationCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("target_type", models.CharField(choices=[("organization", "Organisation"), ("event", "Événement")], max_length=20)),
                ("severity", models.CharField(choices=[("low", "Faible"), ("medium", "Moyenne"), ("high", "Élevée"), ("critical", "Critique")], default="medium", max_length=16)),
                ("status", models.CharField(choices=[("open", "Ouvert"), ("reviewing", "En revue"), ("actioned", "Action appliquée"), ("dismissed", "Classé sans suite")], default="open", max_length=20)),
                ("reason", models.TextField()),
                ("outcome", models.TextField(blank=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderation_cases_assigned", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderation_cases", to="events.event")),
                ("opened_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="moderation_cases_opened", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderation_cases", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="workerheartbeat",
            constraint=models.UniqueConstraint(fields=("worker_name", "instance_id"), name="ops_worker_instance_unique"),
        ),
        migrations.AddIndex(
            model_name="workerheartbeat",
            index=models.Index(fields=["state", "last_seen_at"], name="ops_worker_seen_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsauditlog",
            index=models.Index(fields=["target_type", "target_id", "created_at"], name="ops_audit_target_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsauditlog",
            index=models.Index(fields=["action", "created_at"], name="ops_audit_action_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsincident",
            index=models.Index(fields=["status", "severity", "created_at"], name="ops_inc_status_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsincident",
            index=models.Index(fields=["organization", "status"], name="ops_inc_org_idx"),
        ),
        migrations.AddIndex(
            model_name="operationsincident",
            index=models.Index(fields=["event", "status"], name="ops_inc_event_idx"),
        ),
        migrations.AddIndex(
            model_name="moderationcase",
            index=models.Index(fields=["status", "severity", "created_at"], name="ops_case_status_idx"),
        ),
        migrations.AddIndex(
            model_name="moderationcase",
            index=models.Index(fields=["target_type", "created_at"], name="ops_case_target_idx"),
        ),
    ]

import uuid

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DomainEventOutbox",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=100)),
                ("source_type", models.CharField(max_length=80)),
                ("source_id", models.CharField(blank=True, max_length=128)),
                ("space_id", models.UUIDField(blank=True, null=True)),
                ("activity_id", models.UUIDField(blank=True, null=True)),
                ("payload_version", models.PositiveSmallIntegerField(default=1)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("processing", "En cours"), ("processed", "Traité"), ("failed", "Échoué")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("idempotency_key", models.CharField(max_length=255, unique=True)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="domaineventoutbox",
            index=models.Index(fields=["status", "created_at"], name="de_outbox_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="domaineventoutbox",
            index=models.Index(fields=["event_type", "created_at"], name="de_outbox_type_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="domaineventoutbox",
            constraint=models.CheckConstraint(condition=models.Q(("payload_version__gt", 0)), name="de_outbox_payload_version_pos"),
        ),
        migrations.AddConstraint(
            model_name="domaineventoutbox",
            constraint=models.CheckConstraint(condition=models.Q(("max_attempts__gt", 0)), name="de_outbox_max_attempts_pos"),
        ),
        migrations.CreateModel(
            name="DomainEventConsumption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("consumer", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("processing", "En cours"), ("processed", "Traité"), ("skipped", "Ignoré"), ("failed", "Échoué")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="consumptions", to="core.domaineventoutbox")),
            ],
            options={"ordering": ["event_id", "consumer"]},
        ),
        migrations.AddConstraint(
            model_name="domaineventconsumption",
            constraint=models.UniqueConstraint(fields=("event", "consumer"), name="de_consumption_event_consumer_unique"),
        ),
        migrations.AddConstraint(
            model_name="domaineventconsumption",
            constraint=models.CheckConstraint(condition=models.Q(("max_attempts__gt", 0)), name="de_consumption_max_attempts_pos"),
        ),
        migrations.AddIndex(
            model_name="domaineventconsumption",
            index=models.Index(fields=["event", "status"], name="de_consumer_event_status_idx"),
        ),
        migrations.AddIndex(
            model_name="domaineventconsumption",
            index=models.Index(fields=["consumer", "status"], name="de_consumer_name_status_idx"),
        ),
    ]

# Generated manually for Makolo notifications foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("tickets_issued", "Billets émis"), ("payment_succeeded", "Paiement confirmé"), ("payment_failed", "Paiement échoué"), ("payment_refunded", "Paiement remboursé"), ("event_reminder", "Rappel d’événement"), ("system", "Information système")], default="system", max_length=40)),
                ("category", models.CharField(choices=[("event", "Événement"), ("ticket", "Billetterie"), ("payment", "Paiement"), ("security", "Sécurité"), ("system", "Système"), ("marketing", "Marketing")], default="system", max_length=24)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("action_url", models.CharField(blank=True, max_length=500)),
                ("dedup_key", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="makolo_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("channel", models.CharField(choices=[("email", "E-mail"), ("sms", "SMS"), ("push", "Push")], max_length=16)),
                ("destination", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("queued", "En attente"), ("sent", "Envoyé"), ("failed", "Échoué"), ("skipped", "Ignoré")], default="queued", max_length=16)),
                ("scheduled_for", models.DateTimeField(default=django.utils.timezone.now)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("provider_reference", models.CharField(blank=True, max_length=255)),
                ("last_error", models.TextField(blank=True)),
                ("skipped_reason", models.CharField(blank=True, max_length=255)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="notifications.notification")),
            ],
            options={"ordering": ["scheduled_for", "created_at"]},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "read_at", "created_at"], name="notificatio_recipie_8fdc95_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["category", "created_at"], name="notificatio_categor_b8cdca_idx"),
        ),
        migrations.AddConstraint(
            model_name="notificationdelivery",
            constraint=models.UniqueConstraint(fields=("notification", "channel", "destination"), name="notification_delivery_unique_destination"),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(fields=["status", "scheduled_for"], name="notificatio_status_180fbe_idx"),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(fields=["channel", "status"], name="notificatio_channel_bcd6fa_idx"),
        ),
    ]

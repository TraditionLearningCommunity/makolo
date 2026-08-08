# Generated for Makolo scanner foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("events", "0001_initial"),
        ("tickets", "0002_align_generated_index_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScannerAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(default="Entrée principale", max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agent", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scanner_assignments", to=settings.AUTH_USER_MODEL)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scanner_assignments_created", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scanner_assignments", to="events.event")),
            ],
            options={
                "verbose_name": "affectation scanner",
                "verbose_name_plural": "affectations scanner",
                "ordering": ["event__start_at", "label", "agent__username"],
            },
        ),
        migrations.CreateModel(
            name="ScanLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("result", models.CharField(choices=[("accepted", "Accès autorisé"), ("duplicate", "Billet déjà utilisé"), ("invalid_token", "QR invalide"), ("unknown_ticket", "Billet introuvable"), ("wrong_event", "Mauvais événement"), ("invalid_status", "Billet non valide"), ("event_unavailable", "Événement indisponible")], max_length=32)),
                ("message", models.CharField(max_length=255)),
                ("qr_fingerprint", models.CharField(blank=True, help_text="SHA-256 du jeton présenté. Le QR brut n’est jamais journalisé.", max_length=64)),
                ("client_reference", models.CharField(blank=True, help_text="Identifiant idempotent généré par le terminal de scan.", max_length=64)),
                ("gate", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("scanned_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scan_logs", to="scanner.scannerassignment")),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scan_logs", to="events.event")),
                ("scanner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="scan_logs", to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="scan_logs", to="tickets.ticket")),
            ],
            options={
                "verbose_name": "journal de scan",
                "verbose_name_plural": "journaux de scan",
                "ordering": ["-scanned_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="scannerassignment",
            constraint=models.UniqueConstraint(fields=("event", "agent"), name="scanner_unique_event_agent"),
        ),
        migrations.AddConstraint(
            model_name="scannerassignment",
            constraint=models.CheckConstraint(condition=models.Q(("valid_from__isnull", True), ("valid_until__isnull", True), ("valid_until__gt", models.F("valid_from")), _connector="OR"), name="scanner_assignment_valid_window"),
        ),
        migrations.AddIndex(
            model_name="scannerassignment",
            index=models.Index(fields=["event", "is_active"], name="scanner_assign_event_idx"),
        ),
        migrations.AddIndex(
            model_name="scannerassignment",
            index=models.Index(fields=["agent", "is_active"], name="scanner_assign_agent_idx"),
        ),
        migrations.AddConstraint(
            model_name="scanlog",
            constraint=models.UniqueConstraint(condition=models.Q(("result", "accepted")), fields=("ticket",), name="scanner_one_accept_per_ticket"),
        ),
        migrations.AddConstraint(
            model_name="scanlog",
            constraint=models.UniqueConstraint(condition=models.Q(("client_reference", ""), _negated=True), fields=("scanner", "client_reference"), name="scanner_unique_client_ref"),
        ),
        migrations.AddIndex(
            model_name="scanlog",
            index=models.Index(fields=["event", "scanned_at"], name="scanner_event_time_idx"),
        ),
        migrations.AddIndex(
            model_name="scanlog",
            index=models.Index(fields=["scanner", "scanned_at"], name="scanner_agent_time_idx"),
        ),
        migrations.AddIndex(
            model_name="scanlog",
            index=models.Index(fields=["ticket", "scanned_at"], name="scanner_ticket_time_idx"),
        ),
        migrations.AddIndex(
            model_name="scanlog",
            index=models.Index(fields=["result", "scanned_at"], name="scanner_result_time_idx"),
        ),
    ]

import uuid

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("journeys", "0002_external_beneficiary"),
        ("operations", "0004_occurrence_checkpoints"),
    ]

    operations = [
        migrations.CreateModel(
            name="OccurrenceQueue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=80)),
                ("label", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("open", "Ouverte"), ("paused", "En pause"), ("closed", "Fermée")], default="open", max_length=16)),
                ("next_sequence", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("checkpoint", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="queues", to="operations.occurrencecheckpoint")),
                ("occurrence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="operational_queues", to="activities.occurrence")),
            ],
            options={"ordering": ["occurrence_id", "label", "id"]},
        ),
        migrations.CreateModel(
            name="QueueEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sequence", models.PositiveBigIntegerField()),
                ("status", models.CharField(choices=[("waiting", "En attente"), ("called", "Appelé"), ("served", "Servi"), ("expired", "Expiré"), ("cancelled", "Annulé")], default="waiting", max_length=16)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("client_reference", models.CharField(blank=True, max_length=64)),
                ("entered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("called_at", models.DateTimeField(blank=True, null=True)),
                ("served_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("called_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="queue_entries_called", to=settings.AUTH_USER_MODEL)),
                ("ended_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="queue_entries_ended", to=settings.AUTH_USER_MODEL)),
                ("entered_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="queue_entries_entered", to=settings.AUTH_USER_MODEL)),
                ("external_beneficiary", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_queue_entries", to="journeys.externalbeneficiary")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_queue_entries", to=settings.AUTH_USER_MODEL)),
                ("queue", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="operations.occurrencequeue")),
                ("served_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="queue_entries_served", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["queue_id", "sequence", "id"]},
        ),
        migrations.AddConstraint(model_name="occurrencequeue", constraint=models.UniqueConstraint(fields=("occurrence", "key"), name="ops_queue_occ_key_uq")),
        migrations.AddIndex(model_name="occurrencequeue", index=models.Index(fields=["occurrence", "status"], name="ops_queue_occ_status_idx")),
        migrations.AddConstraint(model_name="queueentry", constraint=models.CheckConstraint(condition=(Q(profile__isnull=False) & Q(external_beneficiary__isnull=True)) | (Q(profile__isnull=True) & Q(external_beneficiary__isnull=False)), name="ops_queue_entry_subject_ck")),
        migrations.AddConstraint(model_name="queueentry", constraint=models.UniqueConstraint(fields=("queue", "sequence"), name="ops_queue_entry_seq_uq")),
        migrations.AddConstraint(model_name="queueentry", constraint=models.UniqueConstraint(condition=Q(profile__isnull=False, status__in=("waiting", "called")), fields=("queue", "profile"), name="ops_queue_active_profile_uq")),
        migrations.AddConstraint(model_name="queueentry", constraint=models.UniqueConstraint(condition=Q(external_beneficiary__isnull=False, status__in=("waiting", "called")), fields=("queue", "external_beneficiary"), name="ops_queue_active_ext_uq")),
        migrations.AddConstraint(model_name="queueentry", constraint=models.UniqueConstraint(condition=~Q(source="") & ~Q(client_reference=""), fields=("queue", "entered_by", "source", "client_reference"), name="ops_queue_entry_client_uq")),
        migrations.AddIndex(model_name="queueentry", index=models.Index(fields=["queue", "status", "sequence"], name="ops_queue_entry_fifo_idx")),
        migrations.AddIndex(model_name="queueentry", index=models.Index(fields=["profile", "status"], name="ops_queue_entry_prof_idx")),
        migrations.AddIndex(model_name="queueentry", index=models.Index(fields=["external_beneficiary", "status"], name="ops_queue_entry_ext_idx")),
    ]

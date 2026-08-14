import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("journeys", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CapacityPool",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(blank=True, max_length=180)),
                ("total_quantity", models.PositiveIntegerField(blank=True, help_text="Laisser vide pour une capacité illimitée.", null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("is_active", models.BooleanField(default=True)),
                ("source_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="capacity_pools", to="activities.activity")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="capacity_pools", to="activities.occurrence")),
            ],
            options={"ordering": ["activity_id", "occurrence_id", "label", "id"]},
        ),
        migrations.CreateModel(
            name="CapacityReservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("status", models.CharField(choices=[("held", "Retenue"), ("committed", "Engagée"), ("released", "Libérée"), ("expired", "Expirée")], default="held", max_length=16)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("committed_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("source_key", models.CharField(blank=True, max_length=180)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="capacity_reservations", to="journeys.journey")),
                ("pool", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="capacity.capacitypool")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(model_name="capacitypool", index=models.Index(fields=["activity", "is_active"], name="capacity_pool_activity_idx")),
        migrations.AddIndex(model_name="capacitypool", index=models.Index(fields=["occurrence", "is_active"], name="capacity_pool_occurrence_idx")),
        migrations.AddConstraint(model_name="capacitypool", constraint=models.CheckConstraint(condition=models.Q(("total_quantity__isnull", True), ("total_quantity__gt", 0), _connector="OR"), name="capacity_pool_total_positive")),
        migrations.AddIndex(model_name="capacityreservation", index=models.Index(fields=["pool", "status"], name="capacity_res_pool_status_idx")),
        migrations.AddIndex(model_name="capacityreservation", index=models.Index(fields=["journey", "status"], name="cap_res_journey_status_idx")),
        migrations.AddIndex(model_name="capacityreservation", index=models.Index(fields=["expires_at", "status"], name="capacity_res_expiry_status_idx")),
        migrations.AddConstraint(model_name="capacityreservation", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="capacity_res_quantity_positive")),
        migrations.AddConstraint(model_name="capacityreservation", constraint=models.UniqueConstraint(condition=models.Q(("source_key", ""), _negated=True), fields=("pool", "journey", "source_key"), name="capacity_res_source_unique")),
    ]

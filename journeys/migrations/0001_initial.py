import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("activities", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Journey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("workflow", models.CharField(choices=[("purchase", "Achat"), ("order_approval", "Commande avec approbation"), ("reservation", "Réservation"), ("registration", "Inscription"), ("invitation", "Invitation")], max_length=32)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumise"), ("pending_approval", "En attente d’approbation"), ("approved", "Approuvée"), ("pending_payment", "En attente de paiement"), ("confirmed", "Confirmée"), ("fulfilled", "Réalisée"), ("rejected", "Rejetée"), ("cancelled", "Annulée"), ("expired", "Expirée")], default="draft", max_length=32)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journeys", to="activities.activity")),
                ("beneficiary", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="beneficiary_journeys", to=settings.AUTH_USER_MODEL)),
                ("initiated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="initiated_journeys", to=settings.AUTH_USER_MODEL)),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="journeys", to="activities.occurrence")),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(fields=["beneficiary", "status"], name="journey_beneficiary_status_idx"),
                    models.Index(fields=["activity", "status"], name="journey_activity_status_idx"),
                    models.Index(fields=["occurrence", "status"], name="journey_occurrence_status_idx"),
                    models.Index(fields=["workflow", "status"], name="journey_workflow_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="JourneyTransition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("from_status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumise"), ("pending_approval", "En attente d’approbation"), ("approved", "Approuvée"), ("pending_payment", "En attente de paiement"), ("confirmed", "Confirmée"), ("fulfilled", "Réalisée"), ("rejected", "Rejetée"), ("cancelled", "Annulée"), ("expired", "Expirée")], max_length=32)),
                ("to_status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumise"), ("pending_approval", "En attente d’approbation"), ("approved", "Approuvée"), ("pending_payment", "En attente de paiement"), ("confirmed", "Confirmée"), ("fulfilled", "Réalisée"), ("rejected", "Rejetée"), ("cancelled", "Annulée"), ("expired", "Expirée")], max_length=32)),
                ("reason", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journey_transitions", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transitions", to="journeys.journey")),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [models.Index(fields=["journey", "created_at"], name="journey_transition_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="JourneyRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(choices=[("approval", "Validation"), ("registration", "Inscription"), ("reservation", "Réservation"), ("invitation", "Invitation"), ("participation", "Participation"), ("other", "Autre")], default="approval", max_length=32)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("approved", "Approuvée"), ("rejected", "Rejetée"), ("cancelled", "Annulée"), ("expired", "Expirée")], default="pending", max_length=16)),
                ("message", models.TextField(blank=True)),
                ("decision_comment", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="journey_requests_decided", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requests", to="journeys.journey")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_requests_made", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(fields=["journey", "status"], name="journey_request_status_idx"),
                    models.Index(fields=["status", "created_at"], name="journey_request_queue_idx"),
                ],
                "constraints": [models.CheckConstraint(condition=Q(("expires_at__isnull", True), ("expires_at__gt", models.F("submitted_at")), _connector="OR"), name="journey_request_expiry_after_submit")],
            },
        ),
    ]

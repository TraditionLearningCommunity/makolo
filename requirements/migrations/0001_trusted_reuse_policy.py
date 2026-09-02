# Generated for Q4 Trusted Reuse.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("opportunities", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequirementReusePolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=80)),
                ("source_type", models.CharField(choices=[("library", "Ma Bibliothèque"), ("journey_artifact", "JourneyArtifact historique"), ("proof", "Proof Trust")], max_length=24)),
                ("artifact_kind", models.CharField(blank=True, choices=[("cv", "CV"), ("cover_letter", "Lettre de motivation"), ("certificate", "Certificat"), ("transcript", "Relevé"), ("recommendation", "Recommandation"), ("identity_document", "Document d’identité"), ("form", "Formulaire"), ("payment_receipt", "Reçu de paiement"), ("other", "Autre")], max_length=32)),
                ("proof_type", models.CharField(blank=True, choices=[("journey_completed", "Journey accomplie"), ("participation_confirmed", "Participation confirmée"), ("access_used", "Accès utilisé"), ("service_completed", "Service complété")], max_length=32)),
                ("require_not_expired", models.BooleanField(default=True)),
                ("max_age_days", models.PositiveIntegerField(blank=True, null=True)),
                ("allow_sensitive_with_confirmation", models.BooleanField(default=False)),
                ("allow_restricted_with_confirmation", models.BooleanField(default=False)),
                ("human_review_required", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reuse_policies", to="opportunities.opportunityrequirement")),
            ],
            options={
                "ordering": ["requirement", "key", "created_at", "id"],
                "indexes": [models.Index(fields=["requirement", "source_type"], name="req_reuse_policy_src_idx")],
                "constraints": [models.UniqueConstraint(fields=("requirement", "key"), name="req_reuse_policy_key_unique")],
            },
        ),
    ]

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("opportunities", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OpportunityRequirementReusePolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("allow_library", models.BooleanField(default=False)),
                ("allow_journey_artifact", models.BooleanField(default=False)),
                ("allow_proof", models.BooleanField(default=False)),
                (
                    "accepted_artifact_kind",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("cv", "CV"),
                            ("cover_letter", "Lettre de motivation"),
                            ("certificate", "Certificat"),
                            ("transcript", "Relevé"),
                            ("recommendation", "Recommandation"),
                            ("identity_document", "Document d’identité"),
                            ("form", "Formulaire"),
                            ("payment_receipt", "Reçu de paiement"),
                            ("other", "Autre"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "accepted_proof_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("journey_completed", "Journey accomplie"),
                            ("participation_confirmed", "Participation confirmée"),
                            ("access_used", "Accès utilisé"),
                            ("service_completed", "Service complété"),
                        ],
                        max_length=32,
                    ),
                ),
                ("max_age_days", models.PositiveIntegerField(blank=True, null=True)),
                ("allow_unknown_freshness", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "requirement",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trusted_reuse_policy",
                        to="opportunities.opportunityrequirement",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="opportunityrequirementreusepolicy",
            constraint=models.CheckConstraint(
                condition=models.Q(("max_age_days__isnull", True), ("max_age_days__gte", 1), _connector="OR"),
                name="opp_reuse_policy_age_positive",
            ),
        ),
    ]

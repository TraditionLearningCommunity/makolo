from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("journeys", "0003_services_core_journey_collaboration"),
        ("payments", "0004_generic_commerce_payment"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentObligation",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("reason", models.CharField(choices=[("commerce", "Commerce"), ("opportunity_requirement", "Requirement Opportunity"), ("service_process", "Processus Service"), ("access_requirement", "Condition d’accès"), ("other", "Autre")], max_length=32)),
                ("label", models.CharField(max_length=220)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.01"))])),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("processing_mode", models.CharField(choices=[("makolo_provider", "Provider Makolo"), ("external", "Paiement externe")], max_length=24)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("processing", "En traitement"), ("satisfied", "Satisfaite"), ("waived", "Dispensée"), ("expired", "Expirée"), ("cancelled", "Annulée"), ("refunded", "Remboursée")], default="pending", max_length=16)),
                ("external_payee_name", models.CharField(blank=True, max_length=220)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("satisfied_at", models.DateTimeField(blank=True, null=True)),
                ("source_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("commerce_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment_obligations", to="commerce.commerceorder")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_payment_obligations", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_obligations", to="journeys.journey")),
                ("payee_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payee_payment_obligations", to=settings.AUTH_USER_MODEL)),
                ("payee_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment_obligations", to="organizations.organization")),
                ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment_obligations", to="journeys.journeystep")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddIndex(model_name="paymentobligation", index=models.Index(fields=["journey", "status"], name="payobl_journey_status_idx")),
        migrations.AddIndex(model_name="paymentobligation", index=models.Index(fields=["step", "status"], name="payobl_step_status_idx")),
        migrations.AddIndex(model_name="paymentobligation", index=models.Index(fields=["commerce_order"], name="payobl_commerce_idx")),
        migrations.AddIndex(model_name="paymentobligation", index=models.Index(fields=["processing_mode", "status"], name="payobl_mode_status_idx")),
        migrations.AddIndex(model_name="paymentobligation", index=models.Index(fields=["due_at", "status"], name="payobl_due_status_idx")),
        migrations.AddConstraint(model_name="paymentobligation", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payobl_amount_positive")),
        migrations.AddConstraint(
            model_name="paymentobligation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("external_payee_name", ""), ("payee_profile__isnull", True), ("payee_space__isnull", False))
                    | models.Q(("external_payee_name", ""), ("payee_profile__isnull", False), ("payee_space__isnull", True))
                    | (models.Q(("payee_profile__isnull", True), ("payee_space__isnull", True)) & ~models.Q(("external_payee_name", "")))
                ),
                name="payobl_exactly_one_payee",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="obligation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="payments.paymentobligation"),
        ),
        migrations.RemoveConstraint(model_name="payment", name="payment_has_order_source"),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(("order__isnull", False)) | models.Q(("commerce_order__isnull", False)) | models.Q(("obligation__isnull", False)), name="payment_has_order_source"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(condition=models.Q(("obligation__isnull", False), ("status", "succeeded")), fields=("obligation",), name="payment_one_success_obligation"),
        ),
        migrations.AddIndex(model_name="payment", index=models.Index(fields=["obligation", "status"], name="pay_obligation_status_idx")),
        migrations.CreateModel(
            name="PaymentEvidence",
            fields=[
                ("id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("external_reference", models.CharField(blank=True, max_length=240)),
                ("paid_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("submitted", "Soumise"), ("verified", "Vérifiée"), ("rejected", "Rejetée")], default="submitted", max_length=16)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_evidence", to="journeys.journeyartifact")),
                ("obligation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evidence", to="payments.paymentobligation")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_payment_evidence", to=settings.AUTH_USER_MODEL)),
                ("verified_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="verified_payment_evidence", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="paymentevidence", constraint=models.UniqueConstraint(fields=("obligation", "artifact"), name="payment_evidence_artifact_unique")),
        migrations.AddIndex(model_name="paymentevidence", index=models.Index(fields=["obligation", "status"], name="payevid_obligation_status_idx")),
    ]

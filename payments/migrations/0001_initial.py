# Generated for Makolo payments foundation.

import decimal
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tickets", "0002_align_generated_index_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(editable=False, max_length=24, unique=True)),
                ("provider", models.CharField(choices=[("sandbox", "Sandbox Makolo"), ("manual", "Manuel")], default="sandbox", max_length=32)),
                ("method", models.CharField(choices=[("card", "Carte"), ("mobile_money", "Mobile Money"), ("bank_transfer", "Virement bancaire"), ("cash", "Espèces"), ("other", "Autre")], default="other", max_length=32)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("processing", "En traitement"), ("succeeded", "Réussi"), ("failed", "Échoué"), ("cancelled", "Annulé"), ("refunded", "Remboursé")], default="pending", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("payer_name", models.CharField(blank=True, max_length=180)),
                ("payer_email", models.EmailField(blank=True, max_length=254)),
                ("payer_phone", models.CharField(blank=True, max_length=40)),
                ("provider_reference", models.CharField(blank=True, max_length=160)),
                ("idempotency_key", models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ("checkout_url", models.URLField(blank=True, max_length=1000)),
                ("failure_code", models.CharField(blank=True, max_length=120)),
                ("failure_message", models.CharField(blank=True, max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("succeeded_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("initiated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="initiated_payments", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="tickets.ticketorder")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Refund",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(editable=False, max_length=24, unique=True)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("succeeded", "Réussi"), ("failed", "Échoué"), ("cancelled", "Annulé")], default="pending", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("provider_reference", models.CharField(blank=True, max_length=160)),
                ("idempotency_key", models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ("failure_message", models.CharField(blank=True, max_length=500)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="payments.payment")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_refunds", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("sandbox", "Sandbox Makolo"), ("manual", "Manuel")], max_length=32)),
                ("event_id", models.CharField(blank=True, max_length=160)),
                ("event_type", models.CharField(max_length=120)),
                ("signature_valid", models.BooleanField(default=False)),
                ("processed", models.BooleanField(default=False)),
                ("payload_hash", models.CharField(max_length=64)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processing_error", models.CharField(blank=True, max_length=500)),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="payments.payment")),
            ],
            options={"ordering": ["-received_at"]},
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["order", "status"], name="pay_order_status_idx"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["provider", "status"], name="pay_provider_status_idx"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["created_at"], name="pay_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payment_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "succeeded")), fields=("order",), name="payment_one_success_order"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(condition=~models.Q(("provider_reference", "")), fields=("provider", "provider_reference"), name="payment_provider_ref_unique"),
        ),
        migrations.AddIndex(
            model_name="refund",
            index=models.Index(fields=["payment", "status"], name="refund_payment_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="refund",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="refund_amount_positive"),
        ),
        migrations.AddConstraint(
            model_name="refund",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "succeeded")), fields=("payment",), name="refund_one_success_payment"),
        ),
        migrations.AddIndex(
            model_name="paymentevent",
            index=models.Index(fields=["provider", "event_type"], name="paye_provider_type_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentevent",
            index=models.Index(fields=["processed", "received_at"], name="paye_processed_idx"),
        ),
        migrations.AddConstraint(
            model_name="paymentevent",
            constraint=models.UniqueConstraint(condition=~models.Q(("event_id", "")), fields=("provider", "event_id"), name="payment_event_provider_unique"),
        ),
    ]

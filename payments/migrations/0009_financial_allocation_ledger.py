from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("payments", "0008_generalize_payment_obligations"),
    ]

    operations = [
        migrations.AddField(
            model_name="refund",
            name="financial_breakdown",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="FinancialAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_kind", models.CharField(choices=[("commerce", "Commerce snapshot"), ("subscription", "Subscription obligation"), ("obligation", "Payment obligation")], max_length=20)),
                ("source_key", models.CharField(max_length=220, unique=True)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("source_snapshot", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("obligation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="financial_allocation", to="payments.paymentobligation")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="FinancialAllocationLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sequence", models.PositiveSmallIntegerField()),
                ("line_type", models.CharField(choices=[("payee", "Bénéficiaire"), ("platform", "Makolo"), ("tax", "Taxe"), ("processing", "Traitement"), ("other", "Autre")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("beneficiary_platform", models.BooleanField(default=False)),
                ("external_beneficiary_name", models.CharField(blank=True, max_length=220)),
                ("source_component_type", models.CharField(blank=True, max_length=40)),
                ("source_component_code", models.CharField(blank=True, max_length=80)),
                ("source_component_index", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("source_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("allocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="payments.financialallocation")),
                ("beneficiary_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="financial_allocation_lines", to=settings.AUTH_USER_MODEL)),
                ("beneficiary_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="financial_allocation_lines", to="organizations.organization")),
            ],
            options={"ordering": ["allocation", "sequence", "id"]},
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("entry_type", models.CharField(choices=[("payment_recognized", "Transaction reconnue"), ("payee_payable", "Payable bénéficiaire"), ("platform_revenue", "Montant Makolo"), ("tax_liability", "Position taxe"), ("processing_reserve", "Composante traitement"), ("other_position", "Autre position"), ("refund", "Remboursement"), ("reversal", "Contre-écriture"), ("adjustment", "Ajustement")], max_length=32)),
                ("economic_role", models.CharField(blank=True, choices=[("payee", "Bénéficiaire"), ("platform", "Makolo"), ("tax", "Taxe"), ("processing", "Traitement"), ("other", "Autre")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("source_kind", models.CharField(choices=[("payment", "Payment"), ("payment_evidence", "PaymentEvidence"), ("refund", "Refund"), ("adjustment", "Ajustement")], max_length=24)),
                ("source_key", models.CharField(max_length=220, unique=True)),
                ("funds_custody", models.CharField(choices=[("unknown", "Non déterminée en F3"), ("external", "Hors garde Makolo")], default="unknown", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("allocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.financialallocation")),
                ("allocation_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.financialallocationline")),
                ("evidence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.paymentevidence")),
                ("obligation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.paymentobligation")),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.payment")),
                ("refund", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.refund")),
            ],
            options={"ordering": ["occurred_at", "created_at", "id"]},
        ),
        migrations.AddIndex(model_name="financialallocation", index=models.Index(fields=["currency", "created_at"], name="finalloc_currency_created_idx")),
        migrations.AddConstraint(model_name="financialallocation", constraint=models.CheckConstraint(condition=models.Q(("total_amount__gt", 0)), name="finalloc_total_positive")),
        migrations.AddIndex(model_name="financialallocationline", index=models.Index(fields=["allocation", "line_type"], name="finline_alloc_role_idx")),
        migrations.AddConstraint(model_name="financialallocationline", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="finline_amount_positive")),
        migrations.AddConstraint(model_name="financialallocationline", constraint=models.UniqueConstraint(fields=("allocation", "sequence"), name="finline_alloc_sequence_unique")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["obligation", "occurred_at"], name="ledger_obligation_time_idx")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["economic_role", "occurred_at"], name="ledger_role_time_idx")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["entry_type", "occurred_at"], name="ledger_type_time_idx")),
        migrations.AddConstraint(model_name="ledgerentry", constraint=models.CheckConstraint(condition=models.Q(("amount", 0), _negated=True), name="ledger_amount_nonzero")),
    ]

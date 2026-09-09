import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("activities", "0005_activity_involvements"),
        ("payments", "0011_alter_payout_amount_alter_settlement_amount"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FundingDetails",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("target_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("minimum_contribution", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("maximum_contribution", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("opens_at", models.DateTimeField(blank=True, null=True)),
                ("closes_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="funding_details", to="activities.activity")),
            ],
            options={"ordering": ["activity__title", "id"]},
        ),
        migrations.CreateModel(
            name="FundingContribution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("currency", models.CharField(max_length=3)),
                ("client_reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("contributor_profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="funding_contributions", to=settings.AUTH_USER_MODEL)),
                ("funding", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="contributions", to="funding.fundingdetails")),
                ("payment_obligation", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="funding_contribution", to="payments.paymentobligation")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="fundingdetails", constraint=models.CheckConstraint(condition=models.Q(("target_amount__isnull", True), ("target_amount__gt", 0), _connector="OR"), name="funding_target_positive")),
        migrations.AddConstraint(model_name="fundingdetails", constraint=models.CheckConstraint(condition=models.Q(("minimum_contribution__isnull", True), ("minimum_contribution__gt", 0), _connector="OR"), name="funding_min_positive")),
        migrations.AddConstraint(model_name="fundingdetails", constraint=models.CheckConstraint(condition=models.Q(("maximum_contribution__isnull", True), ("maximum_contribution__gt", 0), _connector="OR"), name="funding_max_positive")),
        migrations.AddConstraint(model_name="fundingdetails", constraint=models.CheckConstraint(condition=models.Q(("minimum_contribution__isnull", True), ("maximum_contribution__isnull", True), ("maximum_contribution__gte", models.F("minimum_contribution")), _connector="OR"), name="funding_min_lte_max")),
        migrations.AddConstraint(model_name="fundingdetails", constraint=models.CheckConstraint(condition=models.Q(("closes_at__isnull", True), ("opens_at__isnull", True), ("closes_at__gte", models.F("opens_at")), _connector="OR"), name="funding_window_valid")),
        migrations.AddIndex(model_name="fundingcontribution", index=models.Index(fields=["funding", "created_at"], name="funding_contrib_time_idx")),
        migrations.AddIndex(model_name="fundingcontribution", index=models.Index(fields=["contributor_profile", "created_at"], name="funding_profile_time_idx")),
        migrations.AddConstraint(model_name="fundingcontribution", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="funding_contribution_positive")),
        migrations.AddConstraint(model_name="fundingcontribution", constraint=models.UniqueConstraint(condition=models.Q(("client_reference", ""), _negated=True), fields=("funding", "contributor_profile", "client_reference"), name="funding_contribution_client_unique")),
    ]

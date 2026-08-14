import uuid
from decimal import Decimal

from django.conf import settings
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0002_occurrence_place"),
        ("capacity", "0001_initial"),
        ("journeys", "0001_initial"),
        ("organizations", "0003_team_teammembership"),
    ]

    operations = [
        migrations.CreateModel(
            name="Offer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("unit_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("payment_mode", models.CharField(choices=[("none", "Aucun paiement"), ("upfront", "Paiement avant confirmation"), ("after_approval", "Paiement après validation"), ("on_site", "Paiement sur place"), ("later", "Paiement différé")], default="none", max_length=24)),
                ("available_from", models.DateTimeField(blank=True, null=True)),
                ("available_until", models.DateTimeField(blank=True, null=True)),
                ("min_quantity", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("max_quantity", models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)])),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("active", "Active"), ("inactive", "Inactive"), ("archived", "Archivée")], default="draft", max_length=16)),
                ("source_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="offers", to="activities.activity")),
                ("capacity_pool", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="offers", to="capacity.capacitypool")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="offers", to="activities.occurrence")),
            ],
            options={"ordering": ["activity_id", "occurrence_id", "unit_price", "name", "id"]},
        ),
        migrations.CreateModel(
            name="CommerceOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reference", models.CharField(editable=False, max_length=24, unique=True)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("pending", "En attente"), ("confirmed", "Confirmée"), ("cancelled", "Annulée"), ("expired", "Expirée"), ("refunded", "Remboursée")], default="pending", max_length=16)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("payment_mode", models.CharField(choices=[("none", "Aucun paiement"), ("upfront", "Paiement avant confirmation"), ("after_approval", "Paiement après validation"), ("on_site", "Paiement sur place"), ("later", "Paiement différé")], default="none", max_length=24)),
                ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("discount_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("idempotency_key", models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ("source_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("buyer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commerce_orders", to=settings.AUTH_USER_MODEL)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commerce_orders", to="journeys.journey")),
                ("payee_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="commerce_orders", to="organizations.organization")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="CommerceOrderItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("label_snapshot", models.CharField(max_length=180)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("discount_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("beneficiary", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commerce_order_items", to=settings.AUTH_USER_MODEL)),
                ("capacity_reservation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="commerce_items", to="capacity.capacityreservation")),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="commerce.offer")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="commerce.commerceorder")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(model_name="offer", index=models.Index(fields=["activity", "status"], name="commerce_offer_activity_idx")),
        migrations.AddIndex(model_name="offer", index=models.Index(fields=["occurrence", "status"], name="commerce_offer_occurrence_idx")),
        migrations.AddIndex(model_name="offer", index=models.Index(fields=["available_from", "available_until"], name="commerce_offer_window_idx")),
        migrations.AddConstraint(model_name="offer", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="commerce_offer_price_nonnegative")),
        migrations.AddConstraint(model_name="offer", constraint=models.CheckConstraint(condition=models.Q(("max_quantity__isnull", True), ("max_quantity__gte", models.F("min_quantity")), _connector="OR"), name="commerce_offer_quantity_range")),
        migrations.AddConstraint(model_name="offer", constraint=models.CheckConstraint(condition=models.Q(("available_until__isnull", True), ("available_from__isnull", True), ("available_until__gt", models.F("available_from")), _connector="OR"), name="commerce_offer_window_valid")),
        migrations.AddIndex(model_name="commerceorder", index=models.Index(fields=["buyer", "status"], name="commerce_order_buyer_idx")),
        migrations.AddIndex(model_name="commerceorder", index=models.Index(fields=["payee_space", "status"], name="commerce_order_payee_idx")),
        migrations.AddIndex(model_name="commerceorder", index=models.Index(fields=["journey"], name="commerce_order_journey_idx")),
        migrations.AddIndex(model_name="commerceorder", index=models.Index(fields=["created_at"], name="commerce_order_created_idx")),
        migrations.AddConstraint(model_name="commerceorder", constraint=models.CheckConstraint(condition=models.Q(("subtotal__gte", 0)), name="commerce_order_subtotal_nonnegative")),
        migrations.AddConstraint(model_name="commerceorder", constraint=models.CheckConstraint(condition=models.Q(("discount_total__gte", 0)), name="commerce_order_discount_nonnegative")),
        migrations.AddConstraint(model_name="commerceorder", constraint=models.CheckConstraint(condition=models.Q(("total__gte", 0)), name="commerce_order_total_nonnegative")),
        migrations.AddConstraint(model_name="commerceorder", constraint=models.CheckConstraint(condition=models.Q(("discount_total__lte", models.F("subtotal"))), name="commerce_order_discount_lte_subtotal")),
        migrations.AddConstraint(model_name="commerceorder", constraint=models.CheckConstraint(condition=models.Q(("total", models.F("subtotal") - models.F("discount_total"))), name="commerce_order_total_consistent")),
        migrations.AddIndex(model_name="commerceorderitem", index=models.Index(fields=["order"], name="commerce_item_order_idx")),
        migrations.AddIndex(model_name="commerceorderitem", index=models.Index(fields=["offer"], name="commerce_item_offer_idx")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="commerce_item_quantity_positive")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="commerce_item_price_nonnegative")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("line_subtotal__gte", 0)), name="commerce_item_subtotal_nonnegative")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("discount_total__gte", 0)), name="commerce_item_discount_nonnegative")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("line_total__gte", 0)), name="commerce_item_total_nonnegative")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("discount_total__lte", models.F("line_subtotal"))), name="commerce_item_discount_lte_subtotal")),
        migrations.AddConstraint(model_name="commerceorderitem", constraint=models.CheckConstraint(condition=models.Q(("line_total", models.F("line_subtotal") - models.F("discount_total"))), name="commerce_item_total_consistent")),
    ]

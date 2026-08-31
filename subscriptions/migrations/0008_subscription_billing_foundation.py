from decimal import Decimal
import uuid

from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0008_generalize_payment_obligations"),
        ("subscriptions", "0007_subscription_ongoing_requirement_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanVersionBillingTerms",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(Decimal("0.00"))],
                    ),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "billing_period_unit",
                    models.CharField(
                        choices=[("day", "Day"), ("week", "Week"), ("month", "Month"), ("year", "Year")],
                        max_length=8,
                    ),
                ),
                ("billing_period_count", models.PositiveIntegerField(default=1)),
                ("payment_due_days", models.PositiveIntegerField(default=0)),
                ("grace_period_days", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan_version",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_terms",
                        to="subscriptions.planversion",
                    ),
                ),
            ],
            options={
                "ordering": ["plan_version__plan", "plan_version__version"],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionBillingObligation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("billing_key", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "billing_terms",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_obligation_links",
                        to="subscriptions.planversionbillingterms",
                    ),
                ),
                (
                    "obligation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_billing_link",
                        to="payments.paymentobligation",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_obligation_links",
                        to="subscriptions.subscription",
                    ),
                ),
                (
                    "transition",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_obligation_links",
                        to="subscriptions.subscriptiontransition",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(fields=["subscription", "created_at"], name="subs_billing_sub_idx"),
                    models.Index(fields=["transition"], name="subs_billing_transition_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="planversionbillingterms",
            constraint=models.CheckConstraint(condition=models.Q(amount__gte=0), name="subs_billing_amount_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="planversionbillingterms",
            constraint=models.CheckConstraint(condition=models.Q(billing_period_count__gte=1), name="subs_billing_period_positive"),
        ),
        migrations.AddConstraint(
            model_name="subscriptionbillingobligation",
            constraint=models.UniqueConstraint(
                fields=("subscription", "billing_terms", "billing_key"),
                name="subs_billing_obligation_source_unique",
            ),
        ),
    ]

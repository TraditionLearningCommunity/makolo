import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0006_subscription_transitions")]

    operations = [
        migrations.CreateModel(
            name="SubscriptionOngoingRequirementState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("unassessed", "Unassessed"),
                            ("pending", "Pending"),
                            ("satisfied", "Satisfied"),
                            ("unsatisfied", "Unsatisfied"),
                            ("not_applicable", "Not applicable"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reason_code", models.CharField(blank=True, max_length=160)),
                ("first_unsatisfied_at", models.DateTimeField(blank=True, null=True)),
                ("last_evaluated_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan_requirement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_ongoing_states",
                        to="subscriptions.planrequirement",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ongoing_requirement_states",
                        to="subscriptions.subscription",
                    ),
                ),
            ],
            options={"ordering": ["subscription", "plan_requirement__position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="subscriptionongoingrequirementstate",
            constraint=models.UniqueConstraint(
                fields=("subscription", "plan_requirement"),
                name="subs_ongoing_requirement_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionongoingrequirementstate",
            index=models.Index(fields=["subscription", "state"], name="subs_ongoing_state_idx"),
        ),
    ]

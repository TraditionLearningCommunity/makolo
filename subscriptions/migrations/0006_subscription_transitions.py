# Generated for Makolo S4 Subscription Transitions.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0007_payment_obligation_commerce_order_set_null"),
        ("subscriptions", "0005_subscription_requirements"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionTransition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("base_switch", "Changement de BASE"), ("addon_add", "Ajout d’add-on"), ("addon_remove", "Retrait d’add-on")], max_length=20)),
                ("request_origin", models.CharField(choices=[("self_service", "Libre-service"), ("staff", "Staff"), ("system", "Système")], default="self_service", max_length=16)),
                ("status", models.CharField(choices=[("requested", "Demandée"), ("in_progress", "En cours"), ("ready", "Prête"), ("completed", "Terminée"), ("rejected", "Rejetée"), ("cancelled", "Annulée"), ("expired", "Expirée"), ("failed", "Échouée")], default="requested", max_length=16)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("failure_code", models.CharField(blank=True, max_length=120)),
                ("idempotency_key", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requested_subscription_transitions", to=settings.AUTH_USER_MODEL)),
                ("source_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="removal_transitions", to="subscriptions.subscriptionitem")),
                ("source_plan_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subscription_transitions_from", to="subscriptions.planversion")),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transitions", to="subscriptions.subscription")),
                ("target_plan_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscription_transitions_to", to="subscriptions.planversion")),
            ],
            options={"ordering": ["-requested_at", "id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionRequirementAssessment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("state", models.CharField(choices=[("unassessed", "Unassessed"), ("pending", "Pending"), ("satisfied", "Satisfied"), ("unsatisfied", "Unsatisfied"), ("not_applicable", "Not applicable")], default="unassessed", max_length=20)),
                ("reason_code", models.CharField(blank=True, max_length=160)),
                ("actual_value", models.JSONField(blank=True, null=True)),
                ("expected_value", models.JSONField(blank=True, null=True)),
                ("assessed_at", models.DateTimeField(blank=True, null=True)),
                ("last_evaluated_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assessed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="subscription_requirement_assessments", to=settings.AUTH_USER_MODEL)),
                ("plan_requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscription_assessments", to="subscriptions.planrequirement")),
                ("transition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assessments", to="subscriptions.subscriptiontransition")),
            ],
            options={"ordering": ["transition", "plan_requirement__position", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionRequirementAssessmentEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("previous_state", models.CharField(choices=[("unassessed", "Unassessed"), ("pending", "Pending"), ("satisfied", "Satisfied"), ("unsatisfied", "Unsatisfied"), ("not_applicable", "Not applicable")], max_length=20)),
                ("state", models.CharField(choices=[("unassessed", "Unassessed"), ("pending", "Pending"), ("satisfied", "Satisfied"), ("unsatisfied", "Unsatisfied"), ("not_applicable", "Not applicable")], max_length=20)),
                ("reason_code", models.CharField(blank=True, max_length=160)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("assessed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="subscription_requirement_assessment_events", to=settings.AUTH_USER_MODEL)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="subscriptions.subscriptionrequirementassessment")),
            ],
            options={"ordering": ["occurred_at", "id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionTransitionPaymentObligation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_obligation_links", to="subscriptions.subscriptionrequirementassessment")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_subscription_payment_obligation_links", to=settings.AUTH_USER_MODEL)),
                ("obligation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscription_transition_links", to="payments.paymentobligation")),
                ("transition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_obligation_links", to="subscriptions.subscriptiontransition")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddField(
            model_name="subscriptionitem",
            name="created_via_transition",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_items", to="subscriptions.subscriptiontransition"),
        ),
        migrations.AddConstraint(
            model_name="subscriptiontransition",
            constraint=models.UniqueConstraint(fields=("subscription", "idempotency_key"), name="subs_transition_idempotency_unique"),
        ),
        migrations.AddConstraint(
            model_name="subscriptiontransition",
            constraint=models.UniqueConstraint(condition=models.Q(("status__in", ("requested", "in_progress", "ready"))), fields=("subscription",), name="subs_one_open_transition"),
        ),
        migrations.AddIndex(
            model_name="subscriptiontransition",
            index=models.Index(fields=["subscription", "status"], name="subs_transition_status_idx"),
        ),
        migrations.AddIndex(
            model_name="subscriptiontransition",
            index=models.Index(fields=["target_plan_version", "status"], name="subs_transition_target_idx"),
        ),
        migrations.AddConstraint(
            model_name="subscriptionrequirementassessment",
            constraint=models.UniqueConstraint(fields=("transition", "plan_requirement"), name="subs_transition_requirement_unique"),
        ),
        migrations.AddIndex(
            model_name="subscriptionrequirementassessment",
            index=models.Index(fields=["transition", "state"], name="subs_assessment_state_idx"),
        ),
        migrations.AddIndex(
            model_name="subscriptionrequirementassessmentevent",
            index=models.Index(fields=["assessment", "occurred_at"], name="subs_assessment_event_idx"),
        ),
        migrations.AddConstraint(
            model_name="subscriptiontransitionpaymentobligation",
            constraint=models.UniqueConstraint(fields=("assessment", "obligation"), name="subs_assessment_obligation_unique"),
        ),
        migrations.AddConstraint(
            model_name="subscriptiontransitionpaymentobligation",
            constraint=models.UniqueConstraint(fields=("transition", "obligation"), name="subs_transition_obligation_unique"),
        ),
        migrations.AddIndex(
            model_name="subscriptiontransitionpaymentobligation",
            index=models.Index(fields=["transition", "assessment"], name="subs_transition_pay_idx"),
        ),
    ]

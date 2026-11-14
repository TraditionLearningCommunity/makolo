import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("groups", "0005_community_layer"),
        ("subscriptions", "0008_subscription_billing_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="planversionbillingterms",
            name="coverage_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="planversionbillingterms",
            name="coverage_pricing_mode",
            field=models.CharField(
                choices=[("flat", "Forfait"), ("per_seat", "Par bénéficiaire")],
                default="flat", max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="planversionbillingterms",
            name="coverage_max_quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.CreateModel(
            name="SubscriptionCoverage",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("purchased_quantity", models.PositiveIntegerField(validators=[MinValueValidator(1)])),
                ("status", models.CharField(
                    choices=[("pending_payment", "En attente de paiement"), ("active", "Active"), ("suspended", "Suspendue"), ("ended", "Terminée")],
                    default="pending_payment", max_length=20,
                )),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ends_at", models.DateTimeField()),
                ("request_key", models.CharField(max_length=128, unique=True)),
                ("state_reason", models.CharField(blank=True, max_length=320)),
                ("state_changed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payer_profile", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="funded_subscription_coverages", to=settings.AUTH_USER_MODEL,
                )),
                ("payer_space", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="funded_subscription_coverages", to="organizations.organization",
                )),
                ("plan_version", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="funded_coverages", to="subscriptions.planversion",
                )),
                ("billing_terms", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="funded_coverages", to="subscriptions.planversionbillingterms",
                )),
                ("renewal_of", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="renewals", to="subscriptions.subscriptioncoverage",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_funded_coverages", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at", "id"],
                "indexes": [
                    models.Index(fields=["payer_profile", "status"], name="subs_coverage_payer_p_idx"),
                    models.Index(fields=["payer_space", "status"], name="subs_coverage_payer_s_idx"),
                    models.Index(fields=["plan_version", "status"], name="subs_coverage_version_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(payer_profile__isnull=False, payer_space__isnull=True)
                            | models.Q(payer_profile__isnull=True, payer_space__isnull=False)
                        ),
                        name="subs_coverage_payer_xor",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(purchased_quantity__gte=1),
                        name="subs_coverage_quantity_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(ends_at__gt=models.F("starts_at")),
                        name="subs_coverage_window_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionCoverageAllocation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("group_policy", models.CharField(
                    choices=[("current_members", "Membres actuels"), ("snapshot", "Population figée")],
                    default="current_members", max_length=24,
                )),
                ("status", models.CharField(
                    choices=[("invited", "Invitée"), ("active", "Active"), ("declined", "Refusée"), ("revoked", "Révoquée")],
                    default="invited", max_length=16,
                )),
                ("selected_base", models.BooleanField(default=False)),
                ("selected_at", models.DateTimeField(blank=True, null=True)),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ends_at", models.DateTimeField()),
                ("request_key", models.CharField(max_length=128)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("state_changed_at", models.DateTimeField(blank=True, null=True)),
                ("state_reason", models.CharField(blank=True, max_length=320)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("coverage", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="allocations", to="subscriptions.subscriptioncoverage",
                )),
                ("profile", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="subscription_coverage_allocations", to=settings.AUTH_USER_MODEL,
                )),
                ("space", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="subscription_coverage_allocations", to="organizations.organization",
                )),
                ("group", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="subscription_coverage_scopes", to="groups.group",
                )),
                ("group_parent", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="member_allocations", to="subscriptions.subscriptioncoverageallocation",
                )),
                ("group_snapshot", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="subscription_coverage_scopes", to="groups.groupsnapshot",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_coverage_allocations", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(fields=["profile", "status"], name="subs_allocation_prof_idx"),
                    models.Index(fields=["space", "status"], name="subs_allocation_space_idx"),
                    models.Index(fields=["coverage", "status"], name="subs_allocation_pool_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(profile__isnull=False, space__isnull=True, group__isnull=True)
                            | models.Q(profile__isnull=True, space__isnull=False, group__isnull=True)
                            | models.Q(profile__isnull=True, space__isnull=True, group__isnull=False)
                        ),
                        name="subs_allocation_target_xor",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(ends_at__gt=models.F("starts_at")),
                        name="subs_allocation_window_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(selected_base=False) | models.Q(status="active"),
                        name="subs_allocation_selected_active",
                    ),
                    models.UniqueConstraint(
                        fields=["coverage", "request_key"],
                        name="subs_allocation_idempotency",
                    ),
                ],
            },
        ),
        migrations.AlterField(
            model_name="subscriptionbillingobligation",
            name="subscription",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="billing_obligation_links", to="subscriptions.subscription",
            ),
        ),
        migrations.AddField(
            model_name="subscriptionbillingobligation",
            name="coverage",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="billing_obligation_links", to="subscriptions.subscriptioncoverage",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptionbillingobligation",
            constraint=models.UniqueConstraint(
                fields=["coverage", "billing_terms", "billing_key"],
                condition=models.Q(coverage__isnull=False),
                name="subs_billing_coverage_source_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptionbillingobligation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(subscription__isnull=False, coverage__isnull=True)
                    | models.Q(subscription__isnull=True, coverage__isnull=False)
                ),
                name="subs_billing_source_xor",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionbillingobligation",
            index=models.Index(fields=["coverage", "created_at"], name="subs_billing_cov_idx"),
        ),
    ]

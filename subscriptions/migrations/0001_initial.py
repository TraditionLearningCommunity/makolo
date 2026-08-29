# Generated for Makolo S1 Subscription Catalogue & Entitlements Foundation.

import uuid

import django.core.serializers.json
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CODE_VALIDATOR = django.core.validators.RegexValidator(
    message="Utilisez un code technique stable en minuscules (segments séparés par ., _ ou -).",
    regex="^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
)


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="FeatureDefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=120, unique=True, validators=[CODE_VALIDATOR])),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("domain", models.CharField(max_length=80, validators=[CODE_VALIDATOR])),
                ("value_type", models.CharField(choices=[("boolean", "Booléen"), ("integer", "Entier"), ("decimal", "Décimal"), ("enum", "Énumération")], max_length=16)),
                ("unit", models.CharField(blank=True, max_length=40)),
                ("supports_profile", models.BooleanField(default=False)),
                ("supports_space", models.BooleanField(default=False)),
                ("aggregation_strategy", models.CharField(choices=[("BOOLEAN_OR", "Boolean OR"), ("SUM", "Somme"), ("MAX", "Maximum"), ("REPLACE", "Remplacement")], max_length=16)),
                ("usage_provider", models.CharField(blank=True, max_length=120, validators=[CODE_VALIDATOR])),
                ("enforcement_policy", models.CharField(choices=[("feature_gate", "Capacité activée/désactivée"), ("preserve_existing_block_new", "Préserver l’existant et bloquer les nouveaux usages au-delà de la limite")], max_length=40)),
                ("minimum_value", models.DecimalField(blank=True, decimal_places=6, max_digits=20, null=True)),
                ("maximum_value", models.DecimalField(blank=True, decimal_places=6, max_digits=20, null=True)),
                ("enum_values", models.JSONField(blank=True, default=list, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["domain", "code"],
                "indexes": [
                    models.Index(fields=["domain", "is_active"], name="subs_feature_domain_active_idx"),
                    models.Index(fields=["value_type", "is_active"], name="subs_feature_type_active_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("supports_profile", True), ("supports_space", True), _connector="OR"), name="subs_feature_has_subject"),
                    models.CheckConstraint(condition=models.Q(("minimum_value__isnull", True), ("maximum_value__isnull", True), ("minimum_value__lte", models.F("maximum_value")), _connector="OR"), name="subs_feature_value_range"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=120, unique=True, validators=[CODE_VALIDATOR])),
                ("plan_type", models.CharField(choices=[("base", "Base"), ("addon", "Add-on")], max_length=12)),
                ("subject_type", models.CharField(choices=[("profile", "Profil"), ("space", "Espace")], max_length=12)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_subscription_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["subject_type", "plan_type", "code"],
                "indexes": [models.Index(fields=["subject_type", "plan_type", "is_active"], name="subs_plan_subject_type_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("plan_type", "base"), ("is_default", False), _connector="OR"), name="subs_default_only_base"),
                    models.UniqueConstraint(condition=models.Q(("is_active", True), ("is_default", True), ("plan_type", "base")), fields=("subject_type",), name="subs_one_active_default_base"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PlanVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("retired", "Retirée")], default="draft", max_length=12)),
                ("name", models.CharField(max_length=180)),
                ("short_description", models.CharField(blank=True, max_length=320)),
                ("description", models.TextField(blank=True)),
                ("catalog_visibility", models.CharField(choices=[("public", "Publique"), ("unlisted", "Non répertoriée"), ("internal", "Interne")], default="public", max_length=12)),
                ("acquisition_mode", models.CharField(choices=[("self_service", "Libre-service"), ("staff_only", "Staff uniquement")], default="self_service", max_length=16)),
                ("display_order", models.IntegerField(default=0)),
                ("change_summary", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_subscription_plan_versions", to=settings.AUTH_USER_MODEL)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="subscriptions.subscriptionplan")),
            ],
            options={
                "ordering": ["plan", "version"],
                "indexes": [
                    models.Index(fields=["status", "catalog_visibility"], name="subs_version_catalog_idx"),
                    models.Index(fields=["plan", "status"], name="subs_version_plan_status_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("plan", "version"), name="subs_plan_version_unique"),
                    models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="subs_plan_version_positive"),
                ],
            },
        ),
        migrations.AddField(
            model_name="subscriptionplan",
            name="current_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="current_for_plans", to="subscriptions.planversion"),
        ),
        migrations.CreateModel(
            name="PlanBenefit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("icon", models.CharField(blank=True, max_length=80)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_highlighted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="benefits", to="subscriptions.planversion")),
            ],
            options={
                "ordering": ["plan_version", "position", "created_at", "id"],
                "constraints": [models.UniqueConstraint(fields=("plan_version", "position"), name="subs_benefit_position_unique")],
            },
        ),
        migrations.CreateModel(
            name="PlanEntitlement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.JSONField(encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("feature", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="plan_entitlements", to="subscriptions.featuredefinition")),
                ("plan_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entitlements", to="subscriptions.planversion")),
            ],
            options={
                "ordering": ["plan_version", "feature__code"],
                "indexes": [models.Index(fields=["feature", "plan_version"], name="subs_entitlement_lookup_idx")],
                "constraints": [models.UniqueConstraint(fields=("plan_version", "feature"), name="subs_plan_feature_unique")],
            },
        ),
    ]

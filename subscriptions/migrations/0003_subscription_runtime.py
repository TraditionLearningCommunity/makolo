import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0002_seed_feature_definitions"),
        ("organizations", "0004_profilefollow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("grace", "Grâce"), ("suspended", "Suspendue"), ("closed", "Fermée")], default="active", max_length=16)),
                ("grace_until", models.DateTimeField(blank=True, null=True)),
                ("status_reason", models.CharField(blank=True, max_length=320)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="organizations.organization")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("item_type", models.CharField(choices=[("base", "Base"), ("addon", "Add-on")], max_length=12)),
                ("status", models.CharField(choices=[("scheduled", "Planifié"), ("active", "Actif"), ("ended", "Terminé")], default="scheduled", max_length=12)),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("ended_reason", models.CharField(blank=True, max_length=320)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscription_items", to="subscriptions.subscriptionplan")),
                ("plan_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscription_items", to="subscriptions.planversion")),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="subscriptions.subscription")),
            ],
            options={"ordering": ["subscription", "starts_at", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="EntitlementGrant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.JSONField()),
                ("valid_from", models.DateTimeField(default=django.utils.timezone.now)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("reason", models.CharField(max_length=320)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.CharField(blank=True, max_length=320)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("feature", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="grants", to="subscriptions.featuredefinition")),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="entitlement_grants_given", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="entitlement_grants", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="entitlement_grants_revoked", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="entitlement_grants", to="organizations.organization")),
            ],
            options={"ordering": ["-granted_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("profile__isnull", False), ("space__isnull", True)), models.Q(("profile__isnull", True), ("space__isnull", False)), _connector="OR"), name="subs_runtime_subject_xor"),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(condition=models.Q(("profile__isnull", False)), fields=("profile",), name="subs_runtime_one_per_profile"),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(condition=models.Q(("space__isnull", False)), fields=("space",), name="subs_runtime_one_per_space"),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("status", "closed"), _negated=True), ("closed_at__isnull", False), _connector="OR"), name="subs_runtime_closed_has_time"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["status", "grace_until"], name="subs_runtime_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="subscriptionitem",
            constraint=models.UniqueConstraint(condition=models.Q(("item_type", "base"), ("status", "active")), fields=("subscription",), name="subs_item_one_active_base"),
        ),
        migrations.AddConstraint(
            model_name="subscriptionitem",
            constraint=models.UniqueConstraint(condition=models.Q(("item_type", "addon"), ("status", "active")), fields=("subscription", "plan"), name="subs_item_one_active_addon_plan"),
        ),
        migrations.AddConstraint(
            model_name="subscriptionitem",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("status", "ended"), _negated=True), ("ends_at__isnull", False), _connector="OR"), name="subs_item_ended_has_time"),
        ),
        migrations.AddIndex(
            model_name="subscriptionitem",
            index=models.Index(fields=["subscription", "status", "item_type"], name="subs_item_active_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="subscriptionitem",
            index=models.Index(fields=["plan", "status"], name="subs_item_plan_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="entitlementgrant",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("profile__isnull", False), ("space__isnull", True)), models.Q(("profile__isnull", True), ("space__isnull", False)), _connector="OR"), name="subs_grant_subject_xor"),
        ),
        migrations.AddConstraint(
            model_name="entitlementgrant",
            constraint=models.CheckConstraint(condition=models.Q(("valid_until__isnull", True), ("valid_until__gt", models.F("valid_from")), _connector="OR"), name="subs_grant_valid_window"),
        ),
        migrations.AddIndex(
            model_name="entitlementgrant",
            index=models.Index(fields=["profile", "feature", "valid_from"], name="subs_grant_profile_idx"),
        ),
        migrations.AddIndex(
            model_name="entitlementgrant",
            index=models.Index(fields=["space", "feature", "valid_from"], name="subs_grant_space_idx"),
        ),
        migrations.AddIndex(
            model_name="entitlementgrant",
            index=models.Index(fields=["revoked_at", "valid_until"], name="subs_grant_active_idx"),
        ),
    ]

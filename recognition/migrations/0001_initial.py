import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecognitionAccrual",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("accrual_key", models.CharField(max_length=220)),
                ("policy_version", models.CharField(max_length=80)),
                ("channel", models.CharField(choices=[("capacity", "Capacity"), ("coverage", "Coverage"), ("actionability", "Actionability"), ("real_action", "Real Action"), ("economic", "Economic"), ("reliability", "Reliability"), ("durability", "Durability"), ("promotional", "Promotional")], max_length=24)),
                ("cumulative_impact", models.DecimalField(decimal_places=8, default=Decimal("0"), max_digits=24)),
                ("matured_points", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [models.Index(fields=["channel", "updated_at"], name="rec_accrual_channel_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("accrual_key", "policy_version"), name="rec_accrual_key_policy_unique"),
                    models.CheckConstraint(condition=models.Q(("cumulative_impact__gte", 0)), name="rec_accrual_impact_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecognitionCursor",
            fields=[
                ("key", models.CharField(max_length=80, primary_key=True, serialize=False)),
                ("policy_version", models.CharField(max_length=80)),
                ("window_size_hours", models.PositiveSmallIntegerField(default=24)),
                ("last_completed_end", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [models.CheckConstraint(condition=models.Q(("window_size_hours__gte", 1), ("window_size_hours__lte", 168)), name="rec_cursor_window_hours_valid")],
            },
        ),
        migrations.CreateModel(
            name="RecognitionEvaluationWindow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("policy_version", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=16)),
                ("processed_slices", models.PositiveIntegerField(default=0)),
                ("pool_points", models.PositiveBigIntegerField(default=0)),
                ("issued_points", models.PositiveBigIntegerField(default=0)),
                ("unattributed_points", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cursor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evaluation_windows", to="recognition.recognitioncursor")),
            ],
            options={
                "ordering": ["starts_at", "id"],
                "indexes": [models.Index(fields=["cursor", "status", "ends_at"], name="rec_window_status_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("cursor", "starts_at", "ends_at"), name="rec_window_bounds_unique"),
                    models.CheckConstraint(condition=models.Q(("ends_at__gt", models.F("starts_at"))), name="rec_window_order_valid"),
                    models.CheckConstraint(condition=models.Q(("pool_points", models.F("issued_points") + models.F("unattributed_points"))), name="rec_window_points_conserved"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecognitionAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("points_balance", models.PositiveBigIntegerField(default=0)),
                ("lifetime_earned", models.PositiveBigIntegerField(default=0)),
                ("lifetime_spent", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="recognition_accounts", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="recognition_accounts", to="organizations.organization")),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(condition=models.Q(models.Q(("profile__isnull", False), ("space__isnull", True)), models.Q(("profile__isnull", True), ("space__isnull", False)), _connector="OR"), name="rec_account_subject_xor"),
                    models.UniqueConstraint(condition=models.Q(("profile__isnull", False)), fields=("profile",), name="rec_account_profile_unique"),
                    models.UniqueConstraint(condition=models.Q(("space__isnull", False)), fields=("space",), name="rec_account_space_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecognitionSliceReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slice_key", models.CharField(max_length=240, unique=True)),
                ("policy_version", models.CharField(max_length=80)),
                ("channel", models.CharField(choices=[("capacity", "Capacity"), ("coverage", "Coverage"), ("actionability", "Actionability"), ("real_action", "Real Action"), ("economic", "Economic"), ("reliability", "Reliability"), ("durability", "Durability"), ("promotional", "Promotional")], max_length=24)),
                ("temporal_profile", models.CharField(choices=[("pulse", "Pulse"), ("window", "Window"), ("stock", "Stock"), ("flow", "Flow")], max_length=16)),
                ("occurred_at", models.DateTimeField()),
                ("available_at", models.DateTimeField()),
                ("impact_delta", models.DecimalField(decimal_places=8, max_digits=24)),
                ("pool_points", models.PositiveBigIntegerField(default=0)),
                ("issued_points", models.PositiveBigIntegerField(default=0)),
                ("unattributed_points", models.PositiveBigIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accrual", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slice_receipts", to="recognition.recognitionaccrual")),
                ("window", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slice_receipts", to="recognition.recognitionevaluationwindow")),
            ],
            options={
                "ordering": ["available_at", "id"],
                "indexes": [
                    models.Index(fields=["window", "available_at"], name="rec_slice_window_idx"),
                    models.Index(fields=["channel", "occurred_at"], name="rec_slice_channel_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("impact_delta__gte", 0)), name="rec_slice_impact_nonneg"),
                    models.CheckConstraint(condition=models.Q(("pool_points", models.F("issued_points") + models.F("unattributed_points"))), name="rec_slice_points_conserved"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecognitionLedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("grant", "Grant"), ("spend", "Spend"), ("reversal", "Reversal"), ("adjustment", "Adjustment")], max_length=16)),
                ("points", models.BigIntegerField()),
                ("description", models.CharField(max_length=255)),
                ("idempotency_key", models.CharField(max_length=220, unique=True)),
                ("policy_version", models.CharField(blank=True, max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="recognition.recognitionaccount")),
                ("actor_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recognition_ledger_actions", to=settings.AUTH_USER_MODEL)),
                ("recognized_slice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="recognition.recognitionslicereceipt")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["account", "created_at"], name="rec_ledger_account_idx"),
                    models.Index(fields=["kind", "created_at"], name="rec_ledger_kind_idx"),
                ],
                "constraints": [models.CheckConstraint(condition=models.Q(("points", 0), _negated=True), name="rec_ledger_points_nonzero")],
            },
        ),
    ]

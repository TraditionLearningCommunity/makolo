import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_defaults(apps, schema_editor):
    Policy = apps.get_model("recognition", "RecognitionPolicy")
    Rule = apps.get_model("recognition", "RecognitionRule")
    Achievement = apps.get_model("recognition", "AchievementDefinition")
    policy, _ = Policy.objects.get_or_create(
        code="default-network-utility", version=1,
        defaults={
            "name": "Réseau d’action Makolo — défaut",
            "description": "Policy conservatrice par défaut, administrable par nouvelle version.",
            "status": "active",
            "parameters": {"credits_per_utility": "1"},
            "standard_window_hours": 24,
        },
    )
    defaults = (
        ("payment-succeeded", "Paiement réussi", "payment.succeeded", "economic", "2", "pulse"),
        ("payment-refunded", "Remboursement via Makolo", "payment.refunded", "economic", "1", "pulse"),
        ("access-used", "Accès utilisé", "access.used", "real_action", "2", "pulse"),
        ("journey-fulfilled", "Démarche accomplie", "journey.fulfilled", "real_action", "3", "transition"),
        ("opportunity-published", "Information d’opportunité publiée", "opportunity.revision.published", "actionability", "1", "transition"),
        ("journey-from-share", "Partage ayant déclenché une démarche", "journey.started_from_share", "actionability", "1", "pulse"),
        ("checkpoint-closed", "Checkpoint opérationnel conclu", "checkpoint.closed", "real_action", "1", "transition"),
        ("queue-served", "Tour servi", "queue.served", "real_action", "1", "pulse"),
    )
    for code, name, signal, channel, value, temporal in defaults:
        Rule.objects.get_or_create(
            policy=policy, code=code,
            defaults={
                "name": name,
                "signal_kind": signal,
                "channel": channel,
                "measure": {"op": "const", "value": value},
                "normalization": {"kind": "LINEAR", "factor": 1},
                "temporal_profile": temporal,
                "aggregation": "SUM_DISTINCT_OUTCOME",
                "curve": {"kind": "LINEAR", "factor": 1},
                "modulators": ["confidence"],
                "outcome_identity": {"source": "signal.outcome_identity"},
                "attribution": {"strategy": "signal_contributors", "unattributed_allowed": True},
                "priority": 100,
                "enabled": True,
            },
        )
    Achievement.objects.get_or_create(
        code="first-value-created",
        defaults={
            "name": "Première valeur rendue possible",
            "description": "Première contribution Recognition ayant produit au moins un crédit Makolo.",
            "criteria": {"lifetime_earned_gte": 1},
            "badge_label": "Première valeur",
            "is_active": True,
            "is_publicly_presentable": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
    ]
    operations = [
        migrations.AddField(model_name="recognitionaccount", name="pending_points", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="recognitionaccount", name="correction_deficit", field=models.PositiveBigIntegerField(default=0)),
        migrations.AlterField(model_name="recognitionslicereceipt", name="temporal_profile", field=models.CharField(choices=[("pulse", "Pulse"), ("window", "Window"), ("stock", "Stock"), ("flow", "Flow"), ("transition", "Transition")], max_length=16)),
        migrations.CreateModel(name="RecognitionPolicy", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.SlugField(max_length=100)), ("version", models.PositiveIntegerField(default=1)),
            ("name", models.CharField(max_length=180)), ("description", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("draft", "Brouillon"), ("simulated", "Simulée"), ("scheduled", "Planifiée"), ("active", "Active"), ("superseded", "Remplacée"), ("retired", "Retirée")], default="draft", max_length=20)),
            ("effective_from", models.DateTimeField(blank=True, null=True)), ("effective_until", models.DateTimeField(blank=True, null=True)),
            ("parameters", models.JSONField(blank=True, default=dict)), ("standard_window_hours", models.PositiveSmallIntegerField(default=24)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["code", "-version"], "constraints": [models.UniqueConstraint(fields=("code", "version"), name="rec_policy_code_ver_uq")]}),
        migrations.CreateModel(name="RecognitionRule", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("code", models.SlugField(max_length=100)), ("name", models.CharField(max_length=180)), ("signal_kind", models.CharField(max_length=120)),
            ("channel", models.CharField(choices=[("capacity", "Capacity"), ("coverage", "Coverage"), ("actionability", "Actionability"), ("real_action", "Real Action"), ("economic", "Economic"), ("reliability", "Reliability"), ("durability", "Durability"), ("promotional", "Promotional")], default="actionability", max_length=24)),
            ("scope", models.JSONField(blank=True, default=dict)), ("conditions", models.JSONField(blank=True, default=dict)), ("measure", models.JSONField(blank=True, default=dict)),
            ("normalization", models.JSONField(blank=True, default=dict)),
            ("temporal_profile", models.CharField(choices=[("pulse", "Pulse"), ("window", "Window"), ("stock", "Stock"), ("flow", "Flow"), ("transition", "Transition")], default="pulse", max_length=16)),
            ("aggregation", models.CharField(default="SUM", max_length=32)), ("curve", models.JSONField(blank=True, default=dict)),
            ("modulators", models.JSONField(blank=True, default=list)), ("outcome_identity", models.JSONField(blank=True, default=dict)), ("attribution", models.JSONField(blank=True, default=dict)),
            ("combination", models.CharField(choices=[("additive", "Additive"), ("exclusive", "Exclusive"), ("max", "Maximum")], default="additive", max_length=20)),
            ("priority", models.PositiveIntegerField(default=100)), ("enabled", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("policy", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="recognition.recognitionpolicy")),
        ], options={"ordering": ["priority", "code"], "indexes": [models.Index(fields=["policy", "signal_kind", "enabled"], name="rec_rule_signal_idx")], "constraints": [models.UniqueConstraint(fields=("policy", "code"), name="rec_rule_policy_code_uq")]}),
        migrations.CreateModel(name="RecognitionSignal", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("signal_id", models.CharField(max_length=255, unique=True)),
            ("signal_kind", models.CharField(db_index=True, max_length=120)), ("object_type", models.CharField(max_length=120)), ("object_id", models.CharField(max_length=160)),
            ("occurred_at", models.DateTimeField()), ("available_at", models.DateTimeField(db_index=True)), ("outcome_identity", models.CharField(max_length=255)),
            ("values", models.JSONField(blank=True, default=dict)), ("contributors", models.JSONField(blank=True, default=list)),
            ("confidence", models.DecimalField(decimal_places=6, default=Decimal("1"), max_digits=8)), ("source_ref", models.CharField(blank=True, max_length=255)),
            ("processed_at", models.DateTimeField(blank=True, db_index=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"ordering": ["available_at", "created_at"], "indexes": [models.Index(fields=["processed_at", "available_at"], name="rec_signal_pending_idx")], "constraints": [models.UniqueConstraint(fields=("signal_kind", "outcome_identity"), name="rec_signal_outcome_uq")]}),
        migrations.CreateModel(name="RecognitionObjectEvaluation", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("object_type", models.CharField(max_length=120)), ("object_id", models.CharField(max_length=160)),
            ("utility_delta", models.DecimalField(decimal_places=8, max_digits=24)), ("pool_points", models.PositiveBigIntegerField(default=0)), ("unattributed_points", models.PositiveBigIntegerField(default=0)),
            ("explanation", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("receipt", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="object_evaluation", to="recognition.recognitionslicereceipt")),
            ("rule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="evaluations", to="recognition.recognitionrule")),
            ("window", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="object_evaluations", to="recognition.recognitionevaluationwindow")),
        ], options={"ordering": ["-created_at"], "indexes": [models.Index(fields=["object_type", "object_id", "created_at"], name="rec_eval_object_idx")]}),
        migrations.CreateModel(name="RecognitionAllocation", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("causal_mode", models.CharField(choices=[("operate", "Opérer"), ("orchestrate", "Orchestrer"), ("deliver", "Livrer"), ("enable", "Rendre possible"), ("amplify", "Amplifier"), ("maintain", "Maintenir")], default="operate", max_length=20)),
            ("causal_strength", models.DecimalField(decimal_places=10, default=Decimal("0"), max_digits=18)), ("share", models.DecimalField(decimal_places=10, default=Decimal("0"), max_digits=12)),
            ("points", models.PositiveBigIntegerField(default=0)), ("evidence", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="recognition.recognitionaccount")),
            ("evaluation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="recognition.recognitionobjectevaluation")),
        ], options={"constraints": [models.UniqueConstraint(fields=("evaluation", "account", "causal_mode"), name="rec_alloc_eval_acct_uq")]}),
        migrations.CreateModel(name="AchievementDefinition", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("code", models.SlugField(max_length=100, unique=True)),
            ("name", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("criteria", models.JSONField(blank=True, default=dict)),
            ("badge_label", models.CharField(blank=True, max_length=120)), ("is_active", models.BooleanField(default=True)), ("is_publicly_presentable", models.BooleanField(default=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ]),
        migrations.CreateModel(name="AchievementGrant", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("idempotency_key", models.CharField(max_length=220, unique=True)),
            ("evidence", models.JSONField(blank=True, default=dict)), ("granted_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="achievement_grants", to="recognition.recognitionaccount")),
            ("achievement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="grants", to="recognition.achievementdefinition")),
            ("evaluation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="achievement_grants", to="recognition.recognitionobjectevaluation")),
        ], options={"constraints": [models.UniqueConstraint(fields=("achievement", "account"), name="rec_ach_account_uq")]}),
        migrations.CreateModel(name="RewardDefinition", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("code", models.SlugField(max_length=100)), ("version", models.PositiveIntegerField(default=1)),
            ("name", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("kind", models.CharField(choices=[("entitlement", "Entitlement"), ("promotion", "Promotion"), ("access", "Access"), ("introduction", "Introduction"), ("payout", "Payout"), ("other", "Autre")], default="other", max_length=20)),
            ("points_cost", models.PositiveBigIntegerField()), ("fulfillment", models.JSONField(blank=True, default=dict)), ("eligibility", models.JSONField(blank=True, default=dict)),
            ("beneficiary_allowed", models.BooleanField(default=True)), ("acceptance_required", models.BooleanField(default=False)), ("stock", models.PositiveIntegerField(blank=True, null=True)),
            ("valid_from", models.DateTimeField(blank=True, null=True)), ("valid_until", models.DateTimeField(blank=True, null=True)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["name", "-version"], "constraints": [models.UniqueConstraint(fields=("code", "version"), name="rec_reward_code_ver_uq")]}),
        migrations.CreateModel(name="RecognitionRedemption", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("points_cost", models.PositiveBigIntegerField()),
            ("status", models.CharField(choices=[("requested", "Demandée"), ("fulfilled", "Réalisée"), ("cancelled", "Annulée")], default="requested", max_length=20)),
            ("idempotency_key", models.CharField(max_length=220, unique=True)), ("fulfillment_snapshot", models.JSONField(blank=True, default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
            ("beneficiary_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recognition_benefits_received", to=settings.AUTH_USER_MODEL)),
            ("beneficiary_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recognition_benefits_received", to="organizations.organization")),
            ("owner_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="recognition.recognitionaccount")),
            ("reward", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="recognition.rewarddefinition")),
        ], options={"ordering": ["-created_at"], "constraints": [models.CheckConstraint(condition=models.Q(models.Q(("beneficiary_profile__isnull", False), ("beneficiary_space__isnull", True)), models.Q(("beneficiary_profile__isnull", True), ("beneficiary_space__isnull", False)), _connector="OR"), name="rec_redemption_benef_xor")]}),
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
        ("journeys", "0004_fulfillment_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ObtentionDetails",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="obtention_details", to="activities.activity")),
            ],
            options={"ordering": ["activity__title", "id"]},
        ),
        migrations.CreateModel(
            name="ObtentionConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("retired", "Retirée")], default="draft", max_length=16)),
                ("result_label", models.CharField(help_text="Résultat réel permettant de dire que l'obtention est accomplie.", max_length=220)),
                ("target_rule", models.CharField(choices=[("all", "Toutes les cibles"), ("any", "Au moins une cible"), ("at_least_n", "Au moins N cibles")], default="all", max_length=16)),
                ("minimum_targets", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("beneficiary_confirmation_required", models.BooleanField(default=True)),
                ("operator_confirmation_required", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_obtention_configurations", to=settings.AUTH_USER_MODEL)),
                ("obtention", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="configurations", to="obtention.obtentiondetails")),
            ],
            options={"ordering": ["obtention", "-version", "id"]},
        ),
        migrations.CreateModel(
            name="ObtentionTarget",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("characteristics", models.JSONField(blank=True, default=dict)),
                ("quantity", models.DecimalField(decimal_places=3, default=Decimal("1"), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.001"))])),
                ("unit", models.CharField(blank=True, max_length=40)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("configuration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="obtention.obtentionconfiguration")),
            ],
            options={"ordering": ["position", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ObtentionMode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(choices=[("buy", "Achat"), ("rent", "Location"), ("borrow", "Emprunt"), ("receive", "Réception / attribution"), ("exchange", "Échange"), ("other", "Autre")], max_length=16)),
                ("label", models.CharField(blank=True, help_text="Libellé métier optionnel lorsque le contexte exige plus de précision.", max_length=120)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("configuration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modes", to="obtention.obtentionconfiguration")),
            ],
            options={"ordering": ["position", "created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ObtentionJourneyContext",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("plan_materialized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("configuration", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_contexts", to="obtention.obtentionconfiguration")),
                ("journey", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="obtention_context", to="journeys.journey")),
                ("mode", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journey_contexts", to="obtention.obtentionmode")),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.CreateModel(
            name="ObtentionTargetReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("received_quantity", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("beneficiary_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("operator_confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="obtention_target_receipts", to="journeys.journey")),
                ("operator_confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_obtention_receipts", to=settings.AUTH_USER_MODEL)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="obtention.obtentiontarget")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="updated_obtention_receipts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["target__position", "target_id"]},
        ),
        migrations.AddConstraint(
            model_name="obtentionconfiguration",
            constraint=models.UniqueConstraint(fields=("obtention", "version"), name="obtention_configuration_version_unique"),
        ),
        migrations.AddConstraint(
            model_name="obtentionconfiguration",
            constraint=models.CheckConstraint(condition=models.Q(version__gt=0), name="obtention_configuration_version_positive"),
        ),
        migrations.AddConstraint(
            model_name="obtentionconfiguration",
            constraint=models.CheckConstraint(condition=models.Q(minimum_targets__isnull=True) | models.Q(minimum_targets__gt=0), name="obtention_min_targets_positive"),
        ),
        migrations.AddConstraint(
            model_name="obtentionconfiguration",
            constraint=models.UniqueConstraint(condition=models.Q(status="published"), fields=("obtention",), name="obtention_one_published_configuration"),
        ),
        migrations.AddConstraint(
            model_name="obtentiontarget",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="obtention_target_quantity_positive"),
        ),
        migrations.AddIndex(
            model_name="obtentiontarget",
            index=models.Index(fields=["configuration", "position"], name="obtention_target_order_idx"),
        ),
        migrations.AddConstraint(
            model_name="obtentionmode",
            constraint=models.UniqueConstraint(fields=("configuration", "code"), name="obtention_mode_unique"),
        ),
        migrations.AddConstraint(
            model_name="obtentiontargetreceipt",
            constraint=models.UniqueConstraint(fields=("journey", "target"), name="obtention_receipt_target_unique"),
        ),
        migrations.AddConstraint(
            model_name="obtentiontargetreceipt",
            constraint=models.CheckConstraint(condition=models.Q(received_quantity__gte=0), name="obtention_receipt_quantity_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="obtentiontargetreceipt",
            index=models.Index(fields=["journey", "target"], name="obtention_receipt_journey_idx"),
        ),
    ]

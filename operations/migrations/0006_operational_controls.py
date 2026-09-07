from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CONTROL_CODES = (
    "user_signups",
    "access_issuance",
    "payment_creation",
    "autopilot",
)


def seed_operational_controls(apps, schema_editor):
    OperationalControl = apps.get_model("operations", "OperationalControl")
    for code in CONTROL_CODES:
        OperationalControl.objects.get_or_create(code=code, defaults={"is_enabled": True})


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("operations", "0005_occurrence_live_queue"),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationalControl",
            fields=[
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("user_signups", "Nouveaux profils utilisateurs"),
                            ("access_issuance", "Émission de nouveaux Access"),
                            ("payment_creation", "Création de nouveaux paiements"),
                            ("autopilot", "Autopilot"),
                        ],
                        max_length=40,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("reason", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="operations_controls_changed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="operational_controls",
                        to="operations.operationsincident",
                    ),
                ),
            ],
            options={
                "verbose_name": "contrôle opérationnel",
                "verbose_name_plural": "contrôles opérationnels",
                "ordering": ["code"],
            },
        ),
        migrations.RunPython(seed_operational_controls, migrations.RunPython.noop),
    ]

from django.db import migrations, models


OBSERVER_CONTROL_CODE = "observer"


def seed_observer_control(apps, schema_editor):
    OperationalControl = apps.get_model("operations", "OperationalControl")
    OperationalControl.objects.get_or_create(
        code=OBSERVER_CONTROL_CODE,
        defaults={"is_enabled": True},
    )


def remove_observer_control(apps, schema_editor):
    OperationalControl = apps.get_model("operations", "OperationalControl")
    OperationalControl.objects.filter(code=OBSERVER_CONTROL_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0007_queue_eligibility_policy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="operationalcontrol",
            name="code",
            field=models.CharField(
                choices=[
                    ("user_signups", "Nouveaux profils utilisateurs"),
                    ("access_issuance", "Émission de nouveaux Access"),
                    ("payment_creation", "Création de nouveaux paiements"),
                    ("autopilot", "Autopilot"),
                    ("observer", "Observateur"),
                ],
                max_length=40,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.RunPython(
            seed_observer_control,
            remove_observer_control,
        ),
    ]

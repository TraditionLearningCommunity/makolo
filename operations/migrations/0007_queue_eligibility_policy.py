from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0006_operational_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="occurrencequeue",
            name="eligibility_policy",
            field=models.CharField(
                choices=[
                    ("access_required", "Accès requis"),
                    ("journey_required", "Démarche requise"),
                    ("access_or_journey", "Accès ou démarche"),
                ],
                default="access_required",
                help_text="Fait canonique exigé avant l’entrée dans cette file live.",
                max_length=24,
            ),
        ),
    ]

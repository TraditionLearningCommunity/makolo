from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0003_services_core_journey_collaboration"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journey",
            name="workflow",
            field=models.CharField(
                choices=[
                    ("purchase", "Achat"),
                    ("order_approval", "Commande avec approbation"),
                    ("reservation", "Réservation"),
                    ("registration", "Inscription"),
                    ("invitation", "Invitation"),
                    ("service", "Service"),
                    ("fulfillment", "Accomplissement"),
                ],
                max_length=32,
            ),
        ),
    ]

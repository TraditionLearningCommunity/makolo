from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_domain_event_context"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("event", "Événement"),
                    ("ticket", "Billetterie"),
                    ("payment", "Paiement"),
                    ("security", "Sécurité"),
                    ("system", "Système"),
                    ("marketing", "Marketing"),
                    ("service", "Services"),
                    ("opportunity", "Opportunités"),
                ],
                default="system",
                max_length=24,
            ),
        ),
    ]

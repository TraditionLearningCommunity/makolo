from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="archetype",
            field=models.CharField(
                choices=[
                    ("generic", "Espace générique"),
                    ("creative", "Artiste / création"),
                    ("media", "Média / journalisme"),
                    ("education", "Enseignement / formation"),
                    ("transport_operator", "Opérateur de transport"),
                ],
                default="generic",
                db_default="generic",
                help_text="Contexte opérationnel principal de cet Espace. Distinct des Topics et des autorisations.",
                max_length=32,
            ),
        ),
    ]
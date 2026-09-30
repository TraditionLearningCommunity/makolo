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
                    ("commerce", "Commerce / distribution"),
                    ("service_provider", "Prestataire de services"),
                    ("transport_operator", "Opérateur de transport"),
                    ("community", "Association / communauté"),
                ],
                default="generic",
                db_default="generic",
                help_text="Manière principale de fonctionner de cet Espace. Distincte des Topics, verticales, autorisations et Entitlements.",
                max_length=32,
            ),
        ),
    ]
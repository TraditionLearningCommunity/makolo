from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="accessuse",
            name="client_reference",
            field=models.CharField(
                blank=True,
                help_text="Référence idempotente du cycle de contrôle. Aucun credential brut n’est stocké ici.",
                max_length=64,
            ),
        ),
        migrations.AddConstraint(
            model_name="accessuse",
            constraint=models.UniqueConstraint(
                fields=("actor", "client_reference"),
                condition=Q(actor__isnull=False) & ~Q(client_reference=""),
                name="access_use_actor_client_ref_unique",
            ),
        ),
    ]

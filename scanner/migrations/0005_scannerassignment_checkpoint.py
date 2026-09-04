import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0004_occurrence_checkpoints"),
        ("scanner", "0004_event_gate_ordering"),
    ]

    operations = [
        migrations.AddField(
            model_name="scannerassignment",
            name="checkpoint",
            field=models.ForeignKey(
                blank=True,
                help_text="Contexte opérationnel optionnel; ne confère aucune autorité Scanner ou Operations.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scanner_assignments",
                to="operations.occurrencecheckpoint",
            ),
        ),
    ]

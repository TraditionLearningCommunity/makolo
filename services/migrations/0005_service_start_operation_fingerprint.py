from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0004_horizontal_requirement_states"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicejourneycontext",
            name="start_operation_fingerprint",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]

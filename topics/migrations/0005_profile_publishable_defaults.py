from django.db import migrations, models


class Migration(migrations.Migration):
    # Changing defaults does not update existing private selections.
    dependencies = [("topics", "0004_space_open_to_and_match_kinds")]

    operations = [
        migrations.AlterField(
            model_name="profileinterest",
            name="is_public",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="profileopento",
            name="is_public",
            field=models.BooleanField(default=True),
        ),
    ]

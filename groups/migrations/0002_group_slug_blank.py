from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="group",
            name="slug",
            field=models.SlugField(blank=True, max_length=220, unique=True),
        ),
    ]

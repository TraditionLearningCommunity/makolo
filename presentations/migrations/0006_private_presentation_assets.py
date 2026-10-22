from django.db import migrations, models
import presentations.storage


class Migration(migrations.Migration):
    dependencies = [
        ("presentations", "0005_presentationmediause"),
    ]

    operations = [
        migrations.AlterField(
            model_name="presentationasset",
            name="file",
            field=models.FileField(blank=True, upload_to="presentations/assets/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="presentationasset",
            name="private_file",
            field=models.FileField(
                blank=True, null=True, max_length=500,
                storage=presentations.storage.private_presentation_storage,
                upload_to="presentations/assets/%Y/%m/",
            ),
        ),
    ]

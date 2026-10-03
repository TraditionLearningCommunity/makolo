from django.db import migrations, models


def make_demo_profiles_public(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    UserProfile.objects.all().update(public_profile=True, searchable=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_makolo_identifier_social_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="public_profile",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="searchable",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(make_demo_profiles_public, migrations.RunPython.noop),
    ]

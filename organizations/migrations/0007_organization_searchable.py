from django.db import migrations, models


def make_demo_spaces_searchable(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Organization.objects.all().update(searchable=True, public_profile=True)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0006_organization_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="searchable",
            field=models.BooleanField(default=True),
        ),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["searchable", "public_profile"], name="org_search_public_idx"),
        ),
        migrations.RunPython(make_demo_spaces_searchable, migrations.RunPython.noop),
    ]

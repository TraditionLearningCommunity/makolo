from django.db import migrations


def classify_existing_transport_spaces(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    TransportRoute = apps.get_model("transport", "TransportRoute")
    Vehicle = apps.get_model("transport", "Vehicle")

    space_ids = set(
        TransportRoute.objects.exclude(space_id=None).values_list("space_id", flat=True)
    )
    space_ids.update(
        Vehicle.objects.exclude(space_id=None).values_list("space_id", flat=True)
    )
    if space_ids:
        Organization.objects.filter(
            pk__in=space_ids,
            archetype="generic",
        ).update(archetype="transport_operator")


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0005_organization_archetype"),
        ("transport", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            classify_existing_transport_spaces,
            migrations.RunPython.noop,
        ),
    ]
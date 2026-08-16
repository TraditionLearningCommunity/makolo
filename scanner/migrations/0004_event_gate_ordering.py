from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scanner", "0003_activity_occurrence_assignments"),
        ("events", "0007_cutover_event_to_activity"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="eventaccessgate",
            options={"ordering": ["event_id", "priority", "name"]},
        ),
    ]

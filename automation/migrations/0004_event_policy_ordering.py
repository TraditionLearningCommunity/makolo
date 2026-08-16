from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0003_domain_event_rules"),
        ("events", "0007_cutover_event_to_activity"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="eventautomationpolicy",
            options={"ordering": ["event_id"]},
        ),
    ]

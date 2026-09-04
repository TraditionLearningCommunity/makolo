from django.db import migrations


INITIAL_TOPICS = (
    ("technologie", "Technologie"),
    ("entrepreneuriat", "Entrepreneuriat"),
    ("culture", "Culture"),
    ("sport", "Sport"),
    ("formation", "Formation"),
    ("emploi", "Emploi"),
    ("voyage", "Voyage"),
)


def seed_initial_topics(apps, schema_editor):
    Topic = apps.get_model("topics", "Topic")
    for code, label in INITIAL_TOPICS:
        Topic.objects.get_or_create(code=code, defaults={"label": label, "is_active": True})


class Migration(migrations.Migration):
    dependencies = [("topics", "0001_initial")]

    operations = [migrations.RunPython(seed_initial_topics, migrations.RunPython.noop)]

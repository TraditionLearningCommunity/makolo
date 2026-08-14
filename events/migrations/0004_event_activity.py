import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0003_eventvenue_place"), ("activities", "0002_occurrence_place")]
    operations = [migrations.AddField(model_name="event", name="activity", field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="event_vertical", to="activities.activity"))]

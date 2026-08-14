import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0001_initial"),
        ("geography", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="OccurrencePlace",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("primary", "Lieu principal"), ("meeting_point", "Point de rendez-vous"), ("service_point", "Point de service"), ("other", "Autre")], default="other", max_length=24)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("occurrence", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="place_links", to="activities.occurrence")),
                ("place", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="occurrence_links", to="geography.place")),
            ],
            options={"ordering": ["position", "role", "place__name"]},
        ),
        migrations.AddField(
            model_name="occurrence",
            name="places",
            field=models.ManyToManyField(blank=True, related_name="occurrences", through="activities.OccurrencePlace", to="geography.place"),
        ),
        migrations.AddConstraint(model_name="occurrenceplace", constraint=models.UniqueConstraint(fields=("occurrence", "place", "role"), name="activities_occ_place_unique")),
        migrations.AddConstraint(model_name="occurrenceplace", constraint=models.UniqueConstraint(fields=("occurrence",), condition=Q(role="primary"), name="activities_occ_primary_unique")),
        migrations.AddIndex(model_name="occurrenceplace", index=models.Index(fields=["occurrence"], name="activities_occ_place_occ_idx")),
        migrations.AddIndex(model_name="occurrenceplace", index=models.Index(fields=["place"], name="activities_occ_place_geo_idx")),
    ]

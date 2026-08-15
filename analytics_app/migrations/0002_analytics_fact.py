import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("analytics_app", "0001_growthspend"),
        ("core", "0001_domain_events"),
        ("organizations", "0003_team_teammembership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyticsFact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("fact_type", models.CharField(max_length=100)),
                ("numeric_value", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("occurred_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_facts", to="activities.activity")),
                ("domain_event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="analytics_facts", to="core.domaineventoutbox")),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_facts", to="activities.occurrence")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_facts", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_facts", to="organizations.organization")),
            ],
            options={"ordering": ["occurred_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="analyticsfact",
            constraint=models.UniqueConstraint(fields=("domain_event", "fact_type"), name="analytics_fact_event_type_unique"),
        ),
        migrations.AddIndex(
            model_name="analyticsfact",
            index=models.Index(fields=["space", "occurred_at"], name="analytics_fact_space_time_idx"),
        ),
        migrations.AddIndex(
            model_name="analyticsfact",
            index=models.Index(fields=["activity", "occurred_at"], name="analytics_fact_act_time_idx"),
        ),
        migrations.AddIndex(
            model_name="analyticsfact",
            index=models.Index(fields=["occurrence", "occurred_at"], name="analytics_fact_occ_time_idx"),
        ),
        migrations.AddIndex(
            model_name="analyticsfact",
            index=models.Index(fields=["fact_type", "occurred_at"], name="analytics_fact_type_time_idx"),
        ),
    ]

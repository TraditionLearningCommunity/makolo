import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="PersonalGoal",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("goal_type", models.CharField(choices=[("journeys_completed", "Démarches accomplies"), ("activities_completed", "Activities accomplies")], max_length=32)),
                ("target_value", models.PositiveIntegerField()),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("status", models.CharField(choices=[("active", "Actif"), ("completed", "Atteint"), ("paused", "En pause"), ("cancelled", "Annulé")], default="active", max_length=16)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="personal_goals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="personalgoal", constraint=models.CheckConstraint(condition=models.Q(target_value__gt=0), name="goals_target_positive")),
        migrations.AddConstraint(model_name="personalgoal", constraint=models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")), name="goals_period_valid")),
        migrations.AddIndex(model_name="personalgoal", index=models.Index(fields=["profile", "status", "period_end"], name="goals_profile_status_end_idx")),
    ]

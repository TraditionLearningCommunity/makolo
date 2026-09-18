from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prospector_storage", "0002_source_checkpoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospectorfrontierentry",
            name="handoff_generation",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name="prospectorfrontierentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("handoff_generation__gte", 1)),
                name="pros_frontier_handoff_gen_gte_1",
            ),
        ),
    ]

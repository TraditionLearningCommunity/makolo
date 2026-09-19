from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prospector_storage", "0005_feedback_learning"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="prospectorfrontierentry",
            index=models.Index(
                fields=["status", "lease_expires_at", "priority", "id"],
                name="pros_frontier_lease_idx",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("observer_storage", "0002_open_observation_requires_claim"),
    ]

    operations = [
        migrations.AddField(
            model_name="observerscopestate",
            name="lease_token",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="observerscopestate",
            name="lease_expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="observerscopestate",
            name="robots_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="observerscopestate",
            name="robots_expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="observerscopestate",
            name="robots_status",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="observerscopestate",
            name="robots_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddConstraint(
            model_name="observerscopestate",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                    )
                    | models.Q(
                        lease_token__isnull=False,
                        lease_expires_at__isnull=False,
                    )
                ),
                name="obs_scope_lease_consist",
            ),
        ),
        migrations.AddConstraint(
            model_name="observerscopestate",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(robots_status__isnull=True)
                    | models.Q(
                        robots_status__gte=100,
                        robots_status__lte=599,
                    )
                ),
                name="obs_scope_robots_status_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="observerscopestate",
            index=models.Index(
                fields=["scope_kind", "lease_expires_at", "id"],
                name="obs_scope_lease_idx",
            ),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="owner_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_activities",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="activity",
            name="activities_legacy_slug_unique",
        ),
        migrations.AddConstraint(
            model_name="activity",
            constraint=models.CheckConstraint(
                condition=~Q(space__isnull=False, owner_profile__isnull=False),
                name="activities_single_logical_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="activity",
            constraint=models.UniqueConstraint(
                fields=("owner_profile", "slug"),
                condition=Q(owner_profile__isnull=False, space__isnull=True),
                name="activities_profile_slug_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="activity",
            constraint=models.UniqueConstraint(
                fields=("slug",),
                condition=Q(space__isnull=True, owner_profile__isnull=True),
                name="activities_legacy_slug_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="activity",
            index=models.Index(
                fields=["owner_profile", "status"],
                name="activities_owner_status_idx",
            ),
        ),
    ]

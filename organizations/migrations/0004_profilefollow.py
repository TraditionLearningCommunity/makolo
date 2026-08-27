import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_team_teammembership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfileFollow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("notify_new_activities", models.BooleanField(default=True)),
                ("followed_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organizer_profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="profile_followers", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followed_profiles", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-followed_at"]},
        ),
        migrations.AddConstraint(
            model_name="profilefollow",
            constraint=models.UniqueConstraint(fields=("organizer_profile", "user"), name="profile_follow_unique_user"),
        ),
        migrations.AddConstraint(
            model_name="profilefollow",
            constraint=models.CheckConstraint(condition=models.Q(("organizer_profile", models.F("user")), _negated=True), name="profile_follow_no_self"),
        ),
        migrations.AddIndex(
            model_name="profilefollow",
            index=models.Index(fields=["organizer_profile", "followed_at"], name="profile_follow_org_date_idx"),
        ),
        migrations.AddIndex(
            model_name="profilefollow",
            index=models.Index(fields=["user", "followed_at"], name="profile_follow_user_date_idx"),
        ),
    ]

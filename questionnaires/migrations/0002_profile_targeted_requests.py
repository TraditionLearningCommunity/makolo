from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("questionnaires", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="formrequest",
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AlterField(
            model_name="formrequest",
            name="journey",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="form_requests",
                to="journeys.journey",
            ),
        ),
        migrations.AddField(
            model_name="formrequest",
            name="target_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="targeted_form_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="formrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("journey__isnull", False), ("target_profile__isnull", True))
                    | models.Q(("journey__isnull", True), ("target_profile__isnull", False))
                ),
                name="qnr_request_exactly_one_target",
            ),
        ),
        migrations.AddIndex(
            model_name="formrequest",
            index=models.Index(fields=["target_profile", "status"], name="qnr_req_profile_status_idx"),
        ),
    ]

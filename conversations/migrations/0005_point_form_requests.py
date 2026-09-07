import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0004_contact_routes"),
        ("questionnaires", "0002_profile_targeted_requests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationPointFormRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "form_request",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="conversation_point_link",
                        to="questionnaires.formrequest",
                    ),
                ),
                (
                    "point",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="form_request_links",
                        to="conversations.conversationpoint",
                    ),
                ),
                (
                    "target_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversation_form_request_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="conversationpointformrequest",
            constraint=models.UniqueConstraint(
                fields=("point", "target_profile"),
                name="conv_point_form_profile_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationpointformrequest",
            index=models.Index(fields=["target_profile", "point"], name="conv_form_profile_point_idx"),
        ),
    ]

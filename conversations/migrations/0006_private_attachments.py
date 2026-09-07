import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import conversations.media_models
import journeys.storage


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0005_point_form_requests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationPointAttachment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("file", "Fichier"), ("image", "Image"), ("audio", "Audio"), ("voice", "Vocal"), ("video", "Vidéo")], default="file", max_length=16)),
                ("file", models.FileField(max_length=500, storage=journeys.storage.PrivateArtifactStorage(), upload_to=conversations.media_models.conversation_attachment_upload_to)),
                ("original_name", models.CharField(max_length=255)),
                ("mime_type", models.CharField(max_length=180)),
                ("size", models.PositiveBigIntegerField()),
                ("content_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("exchange_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="conversations.pointexchangeentry")),
                ("point", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="conversations.conversationpoint")),
                ("response", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="conversations.conversationpointresponse")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversation_attachments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="conversationpointattachment",
            constraint=models.CheckConstraint(
                condition=models.Q(response__isnull=True) | models.Q(exchange_entry__isnull=True),
                name="conv_attachment_not_response_and_exchange",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationpointattachment",
            index=models.Index(fields=["point", "created_at"], name="conv_attachment_point_idx"),
        ),
        migrations.AddIndex(
            model_name="conversationpointattachment",
            index=models.Index(fields=["uploaded_by", "created_at"], name="conv_attachment_uploader_idx"),
        ),
    ]

import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0007_semantic_point_media"),
        ("groups", "0005_community_layer"),
        ("organizations", "0004_profilefollow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationCollectiveAccess",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("status", models.CharField(max_length=16, default="pending", choices=[
                    ("pending", "En attente"), ("active", "Acceptée"),
                    ("declined", "Refusée"), ("revoked", "Retirée"),
                    ("expired", "Expirée"),
                ])),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="collective_accesses", to="conversations.conversation")),
                ("space", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="conversation_accesses", to="organizations.organization")),
                ("group", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="conversation_accesses", to="groups.group")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="created_conversation_collective_links", to=settings.AUTH_USER_MODEL)),
                ("responded_by", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="decided_conversation_collective_links", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="conversationcollectiveaccess",
            constraint=models.CheckConstraint(
                condition=Q(space__isnull=False, group__isnull=True) |
                    Q(space__isnull=True, group__isnull=False),
                name="conv_collective_exactly_one_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversationcollectiveaccess",
            constraint=models.UniqueConstraint(
                fields=("conversation", "space"), condition=Q(space__isnull=False),
                name="conv_collective_unique_space",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversationcollectiveaccess",
            constraint=models.UniqueConstraint(
                fields=("conversation", "group"), condition=Q(group__isnull=False),
                name="conv_collective_unique_group",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationcollectiveaccess",
            index=models.Index(fields=("conversation", "status"),
                name="conv_collective_conv_status_idx"),
        ),
    ]

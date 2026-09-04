from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("topics", "0002_seed_initial_topics"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfileOpenTo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("participate", "Participer"), ("collaborate", "Collaborer"), ("volunteer", "Bénévolat"), ("speak", "Intervenir / prendre la parole"), ("mentor", "Mentorat"), ("organize", "Organiser"), ("opportunities", "Recevoir des opportunités")], max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("is_public", models.BooleanField(default=False)),
                ("is_searchable", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="open_to_declarations", to=settings.AUTH_USER_MODEL)),
                ("topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="open_to_declarations", to="topics.topic")),
            ],
            options={"ordering": ["kind", "created_at", "id"]},
        ),
        migrations.AddConstraint(model_name="profileopento", constraint=models.UniqueConstraint(fields=("profile", "kind", "topic"), name="topics_profile_open_to_unique")),
        migrations.AddIndex(model_name="profileopento", index=models.Index(fields=["profile", "is_active", "is_public"], name="topic_pot_prof_public_idx")),
        migrations.AddIndex(model_name="profileopento", index=models.Index(fields=["is_active", "is_searchable"], name="topic_pot_search_idx")),
    ]

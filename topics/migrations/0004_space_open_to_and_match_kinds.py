# Generated manually for the action-network convergence.

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        ("topics", "0003_profile_open_to"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profileopento",
            name="kind",
            field=models.CharField(
                choices=[
                    ("participate", "Participer"),
                    ("collaborate", "Collaborer"),
                    ("volunteer", "Bénévolat"),
                    ("speak", "Intervenir / prendre la parole"),
                    ("mentor", "Mentorat"),
                    ("organize", "Organiser"),
                    ("provide_service", "Fournir une prestation"),
                    ("partner", "Partenariat"),
                    ("sponsor", "Sponsoring"),
                    ("opportunities", "Recevoir des opportunités"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="SpaceOpenTo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("participate", "Participer"), ("collaborate", "Collaborer"), ("volunteer", "Bénévolat"), ("speak", "Intervenir / prendre la parole"), ("mentor", "Mentorat"), ("organize", "Organiser"), ("provide_service", "Fournir une prestation"), ("partner", "Partenariat"), ("sponsor", "Sponsoring"), ("opportunities", "Recevoir des opportunités")], max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("is_public", models.BooleanField(default=False)),
                ("is_searchable", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("space", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="open_to_declarations", to="organizations.organization")),
                ("topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="space_open_to_declarations", to="topics.topic")),
            ],
            options={"ordering": ["kind", "created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="spaceopento",
            constraint=models.UniqueConstraint(fields=("space", "kind", "topic"), name="topics_space_open_to_unique"),
        ),
        migrations.AddIndex(
            model_name="spaceopento",
            index=models.Index(fields=["space", "is_active", "is_public"], name="topic_sot_space_public_idx"),
        ),
        migrations.AddIndex(
            model_name="spaceopento",
            index=models.Index(fields=["is_active", "is_searchable", "kind"], name="topic_sot_search_kind_idx"),
        ),
    ]

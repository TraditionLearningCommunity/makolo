import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
        ("organizations", "0004_profilefollow"),
    ]

    operations = [
        migrations.CreateModel(
            name="PresentationTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=160)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("provenance", models.CharField(choices=[("makolo", "Makolo"), ("user", "Utilisateur"), ("space", "Espace")], max_length=16)),
                ("visibility", models.CharField(choices=[("private", "Privé"), ("space", "Espace"), ("public", "Public")], default="private", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_presentation_templates", to=settings.AUTH_USER_MODEL)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_templates", to=settings.AUTH_USER_MODEL)),
                ("owner_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_templates", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="PresentationTheme",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=160)),
                ("name", models.CharField(max_length=180)),
                ("provenance", models.CharField(choices=[("makolo", "Makolo"), ("user", "Utilisateur"), ("space", "Espace")], max_length=16)),
                ("visibility", models.CharField(choices=[("private", "Privé"), ("space", "Espace"), ("public", "Public")], default="private", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_presentation_themes", to=settings.AUTH_USER_MODEL)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_themes", to=settings.AUTH_USER_MODEL)),
                ("owner_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="presentation_themes", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="PresentationTemplateVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version_number", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumis"), ("published", "Publié"), ("retired", "Retiré"), ("suspended", "Suspendu")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("manifest", models.JSONField(default=dict)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="presentations.presentationtemplate")),
            ],
        ),
        migrations.CreateModel(
            name="PresentationThemeVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version_number", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumis"), ("published", "Publié"), ("retired", "Retiré"), ("suspended", "Suspendu")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("tokens", models.JSONField(default=dict)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("theme", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="presentations.presentationtheme")),
            ],
        ),
        migrations.CreateModel(
            name="ActivityPresentation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(choices=[("public_page", "Page publique"), ("invitation", "Invitation"), ("access_pass", "Billet / Access"), ("confirmation", "Confirmation"), ("program", "Programme"), ("badge", "Badge")], max_length=24)),
                ("editorial_data", models.JSONField(blank=True, default=dict)),
                ("visual_overrides", models.JSONField(blank=True, default=dict)),
                ("state", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publié"), ("archived", "Archivé")], default="draft", max_length=16)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="presentations", to="activities.activity")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_activity_presentations", to=settings.AUTH_USER_MODEL)),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="presentations", to="activities.occurrence")),
                ("template_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="activity_bindings", to="presentations.presentationtemplateversion")),
                ("theme_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="activity_bindings", to="presentations.presentationthemeversion")),
            ],
        ),
        migrations.AddConstraint(model_name="presentationtemplate", constraint=models.CheckConstraint(condition=~models.Q(("owner_profile__isnull", False), ("owner_space__isnull", False)), name="mps_template_single_owner")),
        migrations.AddConstraint(model_name="presentationtemplate", constraint=models.UniqueConstraint(condition=models.Q(("owner_profile__isnull", False)), fields=("owner_profile", "slug"), name="mps_template_profile_slug_unique")),
        migrations.AddConstraint(model_name="presentationtemplate", constraint=models.UniqueConstraint(condition=models.Q(("owner_space__isnull", False)), fields=("owner_space", "slug"), name="mps_template_space_slug_unique")),
        migrations.AddConstraint(model_name="presentationtemplate", constraint=models.UniqueConstraint(condition=models.Q(("provenance", "makolo")), fields=("slug",), name="mps_template_makolo_slug_unique")),
        migrations.AddConstraint(model_name="presentationtheme", constraint=models.CheckConstraint(condition=~models.Q(("owner_profile__isnull", False), ("owner_space__isnull", False)), name="mps_theme_single_owner")),
        migrations.AddConstraint(model_name="presentationtemplateversion", constraint=models.UniqueConstraint(fields=("template", "version_number"), name="mps_template_version_unique")),
        migrations.AddConstraint(model_name="presentationthemeversion", constraint=models.UniqueConstraint(fields=("theme", "version_number"), name="mps_theme_version_unique")),
        migrations.AddConstraint(model_name="activitypresentation", constraint=models.UniqueConstraint(condition=models.Q(("occurrence__isnull", True)), fields=("activity", "purpose"), name="mps_activity_purpose_unique")),
        migrations.AddConstraint(model_name="activitypresentation", constraint=models.UniqueConstraint(condition=models.Q(("occurrence__isnull", False)), fields=("occurrence", "purpose"), name="mps_occurrence_purpose_unique")),
        migrations.AddIndex(model_name="activitypresentation", index=models.Index(fields=["activity", "purpose", "state"], name="mps_activity_purpose_state_idx")),
    ]

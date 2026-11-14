import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Additive only. Existing is_public flags and existing profile choices remain intact.
class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_passport_public_defaults"),
        ("groups", "0005_community_layer"),
        ("organizations", "0007_organization_searchable"),
        ("topics", "0004_space_open_to_and_match_kinds"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProfileVisibilityPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("target_kind", models.CharField(choices=[
                    ("field", "Information de profil"),
                    ("interest", "Centre d'intérêt"),
                    ("open_to", "Ouvert à"),
                ], max_length=16)),
                ("field_key", models.CharField(blank=True, default="", max_length=48)),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="visibility_policies",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("interest", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="visibility_policies",
                    to="topics.profileinterest",
                )),
                ("open_to", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="visibility_policies",
                    to="topics.profileopento",
                )),
            ],
        ),
        migrations.CreateModel(
            name="ProfileVisibilityAudience",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[
                    ("public", "Tout le monde"),
                    ("my_collectives", "Mes collectifs"),
                    ("selected_space", "Espace choisi"),
                    ("selected_team", "Équipe choisie"),
                    ("selected_group", "Groupe choisi"),
                    ("selected_profile", "Personne choisie"),
                ], max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("policy", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="audiences",
                    to="accounts.profilevisibilitypolicy",
                )),
                ("selected_profile", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profile_visibility_grants_received",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("selected_space", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profile_visibility_audiences",
                    to="organizations.organization",
                )),
                ("selected_team", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profile_visibility_audiences",
                    to="organizations.team",
                )),
                ("selected_group", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profile_visibility_audiences",
                    to="groups.group",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="profilevisibilitypolicy",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        target_kind="field",
                        field_key__in=(
                            "name", "avatar", "bio", "profession", "country",
                            "city", "company_name", "organization_name",
                            "website", "linkedin_url", "facebook_url",
                            "instagram_url", "tiktok_url", "x_url", "youtube_url",
                        ),
                        interest__isnull=True,
                        open_to__isnull=True,
                    )
                    | models.Q(target_kind="interest", field_key="", interest__isnull=False, open_to__isnull=True)
                    | models.Q(target_kind="open_to", field_key="", interest__isnull=True, open_to__isnull=False)
                ),
                name="prof_visibility_target_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilitypolicy",
            constraint=models.UniqueConstraint(
                fields=("owner", "field_key"), condition=models.Q(target_kind="field"),
                name="prof_vis_uniq_field",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilitypolicy",
            constraint=models.UniqueConstraint(
                fields=("owner", "interest"), condition=models.Q(target_kind="interest"),
                name="prof_vis_uniq_interest",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilitypolicy",
            constraint=models.UniqueConstraint(
                fields=("owner", "open_to"), condition=models.Q(target_kind="open_to"),
                name="prof_vis_uniq_open_to",
            ),
        ),
        migrations.AddIndex(
            model_name="profilevisibilitypolicy",
            index=models.Index(fields=["owner", "target_kind"], name="prof_visibility_owner_idx"),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        kind__in=("public", "my_collectives"),
                        selected_profile__isnull=True, selected_space__isnull=True,
                        selected_team__isnull=True, selected_group__isnull=True,
                    )
                    | models.Q(
                        kind="selected_profile", selected_profile__isnull=False,
                        selected_space__isnull=True, selected_team__isnull=True,
                        selected_group__isnull=True,
                    )
                    | models.Q(
                        kind="selected_space", selected_profile__isnull=True,
                        selected_space__isnull=False, selected_team__isnull=True,
                        selected_group__isnull=True,
                    )
                    | models.Q(
                        kind="selected_team", selected_profile__isnull=True,
                        selected_space__isnull=True, selected_team__isnull=False,
                        selected_group__isnull=True,
                    )
                    | models.Q(
                        kind="selected_group", selected_profile__isnull=True,
                        selected_space__isnull=True, selected_team__isnull=True,
                        selected_group__isnull=False,
                    )
                ),
                name="prof_visibility_audience_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.UniqueConstraint(
                fields=("policy", "kind"),
                condition=models.Q(kind__in=("public", "my_collectives")),
                name="prof_vis_uniq_broad",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.UniqueConstraint(
                fields=("policy", "selected_profile"),
                condition=models.Q(kind="selected_profile"),
                name="prof_vis_uniq_profile",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.UniqueConstraint(
                fields=("policy", "selected_space"),
                condition=models.Q(kind="selected_space"),
                name="prof_vis_uniq_space",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.UniqueConstraint(
                fields=("policy", "selected_team"),
                condition=models.Q(kind="selected_team"),
                name="prof_vis_uniq_team",
            ),
        ),
        migrations.AddConstraint(
            model_name="profilevisibilityaudience",
            constraint=models.UniqueConstraint(
                fields=("policy", "selected_group"),
                condition=models.Q(kind="selected_group"),
                name="prof_vis_uniq_group",
            ),
        ),
        migrations.AddIndex(
            model_name="profilevisibilityaudience",
            index=models.Index(fields=["policy", "kind"], name="prof_visibility_aud_idx"),
        ),
    ]

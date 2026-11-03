from django.db import migrations, models


# Keep database checks aligned with the explicit, published-field allowlist
# in accounts.models. This expands the accepted field targets without relaxing
# the per-owner or per-audience visibility rules.
PUBLISHABLE_FIELDS = (
    "name",
    "avatar",
    "bio",
    "profession",
    "country",
    "city",
    "company_name",
    "organization_name",
    "website",
    "linkedin_url",
    "facebook_url",
    "instagram_url",
    "tiktok_url",
    "x_url",
    "youtube_url",
    "interests",
    "open_to",
)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_profile_visibility_policies"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="profilevisibilitypolicy",
            name="prof_visibility_target_shape",
        ),
        migrations.AddConstraint(
            model_name="profilevisibilitypolicy",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        target_kind="field",
                        field_key__in=PUBLISHABLE_FIELDS,
                        interest__isnull=True,
                        open_to__isnull=True,
                    )
                    | models.Q(
                        target_kind="interest",
                        field_key="",
                        interest__isnull=False,
                        open_to__isnull=True,
                    )
                    | models.Q(
                        target_kind="open_to",
                        field_key="",
                        interest__isnull=True,
                        open_to__isnull=False,
                    )
                ),
                name="prof_visibility_target_shape",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("presentations", "0003_space_defaults_and_moderation")]

    operations = [
        migrations.AddConstraint(
            model_name="presentationtheme",
            constraint=models.UniqueConstraint(condition=models.Q(("owner_profile__isnull", False)), fields=("owner_profile", "slug"), name="mps_theme_profile_slug_unique"),
        ),
        migrations.AddConstraint(
            model_name="presentationtheme",
            constraint=models.UniqueConstraint(condition=models.Q(("owner_space__isnull", False)), fields=("owner_space", "slug"), name="mps_theme_space_slug_unique"),
        ),
        migrations.AddConstraint(
            model_name="presentationtheme",
            constraint=models.UniqueConstraint(condition=models.Q(("provenance", "makolo")), fields=("slug",), name="mps_theme_makolo_slug_unique"),
        ),
    ]

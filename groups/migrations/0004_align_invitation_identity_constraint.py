from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0003_invitation_identity_verification"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="groupinvitation",
            name="groups_invitation_has_identity",
        ),
        migrations.AddConstraint(
            model_name="groupinvitation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(profile__isnull=False)
                    | ~models.Q(email="")
                    | ~models.Q(phone="")
                    | ~models.Q(external_reference="")
                ),
                name="groups_invitation_has_identity",
            ),
        ),
    ]

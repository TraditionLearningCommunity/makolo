import geography.validators
from django.db import migrations, models
from django.db.models import Q


SAFE_GENDER_MAP = {
    "m": "male",
    "male": "male",
    "man": "male",
    "homme": "male",
    "masculin": "male",
    "f": "female",
    "female": "female",
    "woman": "female",
    "femme": "female",
    "féminin": "female",
    "feminin": "female",
    "unspecified": "unspecified",
    "unknown": "unspecified",
    "non renseigné": "unspecified",
    "non renseigne": "unspecified",
}


def normalize_known_gender_values(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(gender__isnull=True).update(gender="unspecified")
    User.objects.filter(gender="").update(gender="unspecified")
    for user in User.objects.exclude(gender__isnull=True).exclude(gender="").only("pk", "gender").iterator():
        raw = (user.gender or "").strip()
        mapped = SAFE_GENDER_MAP.get(raw.casefold())
        if mapped and mapped != user.gender:
            User.objects.filter(pk=user.pk).update(gender=mapped)


def preserve_gender_values(apps, schema_editor):
    # Reverse intentionally preserves the stable canonical codes. Reconstructing
    # an arbitrary historical spelling would be less faithful than leaving the
    # normalized value in place.
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_account_ux_defaults"),
    ]

    operations = [
        migrations.RunPython(normalize_known_gender_values, preserve_gender_values),
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("male", "Homme"),
                    ("female", "Femme"),
                    ("unspecified", "Non renseigné"),
                ],
                default="unspecified",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="language",
            field=models.CharField(
                choices=[("fr", "Français")],
                default="fr",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="timezone",
            field=models.CharField(
                default="Africa/Lubumbashi",
                max_length=100,
                validators=[geography.validators.validate_timezone_name],
            ),
        ),
        migrations.AddField(
            model_name="userdevice",
            name="device_key_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddConstraint(
            model_name="userdevice",
            constraint=models.UniqueConstraint(
                fields=("user", "device_key_hash"),
                condition=~Q(device_key_hash=""),
                name="accounts_device_user_key_unique",
            ),
        ),
    ]

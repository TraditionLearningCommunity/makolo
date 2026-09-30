from django.db import migrations, models


def backfill_legacy_suspensions(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Organization.objects.filter(verification_status="suspended").update(
        lifecycle="suspended"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0005_organization_archetype"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="lifecycle",
            field=models.CharField(
                choices=[("active", "Actif"), ("suspended", "Suspendu"), ("archived", "Archivé")],
                db_default="active",
                default="active",
                help_text="État opérationnel de l'Espace, distinct de sa vérification Trust.",
                max_length=16,
            ),
        ),
        migrations.RunPython(backfill_legacy_suspensions, reverse_code=migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["lifecycle", "public_profile"], name="org_lifecycle_public_idx"),
        ),
    ]

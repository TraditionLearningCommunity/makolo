from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def forwards(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Organization = apps.get_model("organizations", "Organization")
    Membership = apps.get_model("organizations", "OrganizationMembership")
    User = apps.get_model("accounts", "User")

    organization_by_user = {}
    organizer_ids = Event.objects.exclude(organizer_id=None).values_list("organizer_id", flat=True).distinct()
    for organizer_id in organizer_ids:
        user = User.objects.get(pk=organizer_id)
        display = f"{user.first_name} {user.last_name}".strip() or user.username or user.email.split("@")[0]
        base = slugify(f"{display}-events")[:170] or f"organizer-{str(user.pk)[:8]}"
        slug = base
        suffix = 2
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base[:185]}-{suffix}"
            suffix += 1
        org = Organization.objects.create(
            name=f"{display} Events",
            slug=slug,
            created_by_id=user.pk,
            contact_email=user.email or "",
            public_profile=True,
        )
        Membership.objects.create(
            organization_id=org.pk,
            user_id=user.pk,
            role="owner",
            is_active=True,
            invited_by_id=user.pk,
        )
        organization_by_user[user.pk] = org.pk

    for event in Event.objects.filter(organization_id=None).iterator():
        event.organization_id = organization_by_user.get(event.organizer_id)
        event.save(update_fields=["organization"])


def backwards(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Event.objects.update(organization_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0001_initial"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="organizations.organization",
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["organization", "status", "start_at"], name="events_even_organiz_b26406_idx"),
        ),
        migrations.RunPython(forwards, backwards),
    ]

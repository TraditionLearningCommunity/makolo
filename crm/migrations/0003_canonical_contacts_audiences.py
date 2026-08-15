import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def deduplicate_profile_contacts(apps, schema_editor):
    CRMContact = apps.get_model("crm", "CRMContact")
    CRMContactTag = apps.get_model("crm", "CRMContactTag")
    CRMContactFieldValue = apps.get_model("crm", "CRMContactFieldValue")
    CampaignRecipient = apps.get_model("crm", "CampaignRecipient")
    CRMContactNote = apps.get_model("crm", "CRMContactNote")
    CampaignAttribution = apps.get_model("crm", "CampaignAttribution")

    duplicates = (
        CRMContact.objects.exclude(user_id__isnull=True)
        .values("organization_id", "user_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
    )
    for row in duplicates.iterator():
        contacts = list(
            CRMContact.objects.filter(
                organization_id=row["organization_id"], user_id=row["user_id"]
            ).order_by("first_seen_at", "created_at", "id")
        )
        canonical = contacts[0]
        for duplicate in contacts[1:]:
            for link in CRMContactTag.objects.filter(contact_id=duplicate.pk):
                CRMContactTag.objects.get_or_create(
                    contact_id=canonical.pk,
                    tag_id=link.tag_id,
                    defaults={"assigned_by_id": link.assigned_by_id},
                )
            CRMContactTag.objects.filter(contact_id=duplicate.pk).delete()

            for value in CRMContactFieldValue.objects.filter(contact_id=duplicate.pk):
                existing = CRMContactFieldValue.objects.filter(
                    contact_id=canonical.pk, field_id=value.field_id
                ).first()
                if existing is None:
                    CRMContactFieldValue.objects.filter(pk=value.pk).update(contact_id=canonical.pk)
                else:
                    CRMContactFieldValue.objects.filter(pk=value.pk).delete()

            for recipient in CampaignRecipient.objects.filter(contact_id=duplicate.pk):
                existing = CampaignRecipient.objects.filter(
                    campaign_id=recipient.campaign_id, contact_id=canonical.pk
                ).first()
                if existing:
                    CampaignAttribution.objects.filter(recipient_id=recipient.pk).update(recipient_id=existing.pk)
                    CampaignRecipient.objects.filter(pk=recipient.pk).delete()
                else:
                    CampaignRecipient.objects.filter(pk=recipient.pk).update(contact_id=canonical.pk)

            CRMContactNote.objects.filter(contact_id=duplicate.pk).update(contact_id=canonical.pk)
            CampaignAttribution.objects.filter(contact_id=duplicate.pk).update(contact_id=canonical.pk)

            canonical.first_seen_at = min(canonical.first_seen_at, duplicate.first_seen_at)
            canonical.last_seen_at = max(canonical.last_seen_at, duplicate.last_seen_at)
            if not canonical.name and duplicate.name:
                canonical.name = duplicate.name
            if not canonical.phone and duplicate.phone:
                canonical.phone = duplicate.phone
            consents = {canonical.marketing_consent, duplicate.marketing_consent}
            if "unsubscribed" in consents:
                canonical.marketing_consent = "unsubscribed"
            elif "subscribed" in consents:
                canonical.marketing_consent = "subscribed"
            CRMContact.objects.filter(pk=duplicate.pk).delete()
        canonical.save()


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_occurrence_place"),
        ("core", "0001_domain_events"),
        ("crm", "0002_followers_tags_fields_templates_attribution"),
        ("groups", "0004_align_invitation_identity_constraint"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(deduplicate_profile_contacts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="crmcontact",
            constraint=models.UniqueConstraint(
                fields=("organization", "user"),
                condition=Q(user__isnull=False),
                name="crm_contact_org_profile_unique",
            ),
        ),
        migrations.CreateModel(
            name="CRMInteraction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("interaction_type", models.CharField(choices=[("journey.submitted", "Démarche soumise"), ("journey.confirmed", "Démarche confirmée"), ("journey.fulfilled", "Démarche réalisée"), ("access.issued", "Accès émis"), ("access.used", "Accès utilisé"), ("commerce.order.confirmed", "Commande confirmée"), ("payment.succeeded", "Paiement réussi"), ("group.membership.active", "Membre d’un Groupe"), ("legacy.event", "Interaction Event historique")], max_length=48)),
                ("occurred_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_interactions", to="activities.activity")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interactions", to="crm.crmcontact")),
                ("domain_event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_interactions", to="core.domaineventoutbox")),
            ],
            options={"ordering": ["-occurred_at", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="crminteraction",
            constraint=models.UniqueConstraint(fields=("contact", "domain_event", "interaction_type"), condition=Q(domain_event__isnull=False), name="crm_interaction_event_type_unique"),
        ),
        migrations.AddIndex(model_name="crminteraction", index=models.Index(fields=["contact", "occurred_at"], name="crm_interact_contact_dt_idx")),
        migrations.AddIndex(model_name="crminteraction", index=models.Index(fields=["domain_event"], name="crm_interaction_event_idx")),
        migrations.CreateModel(
            name="Audience",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("archived", "Archivée")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_crm_audiences", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crm_audiences", to="organizations.organization")),
                ("source_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_audiences", to="groups.group")),
                ("source_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_audiences", to="groups.groupsnapshot")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(model_name="audience", constraint=models.UniqueConstraint(fields=("organization", "name"), name="crm_audience_org_name_unique")),
        migrations.AddIndex(model_name="audience", index=models.Index(fields=["organization", "status"], name="crm_audience_org_status_idx")),
        migrations.CreateModel(
            name="AudienceMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(choices=[("manual", "Ajout manuel"), ("group", "Groupe"), ("group_snapshot", "Snapshot de Groupe")], default="manual", max_length=24)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("audience", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="crm.audience")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_audience_memberships", to=settings.AUTH_USER_MODEL)),
                ("source_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_audience_members", to="groups.group")),
                ("source_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_audience_members", to="groups.groupsnapshot")),
            ],
            options={"ordering": ["profile__email"]},
        ),
        migrations.AddConstraint(model_name="audiencemember", constraint=models.UniqueConstraint(fields=("audience", "profile"), name="crm_audience_member_unique")),
        migrations.AddIndex(model_name="audiencemember", index=models.Index(fields=["profile"], name="crm_aud_member_profile_idx")),
    ]

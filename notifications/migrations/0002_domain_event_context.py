from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("core", "0001_domain_events"),
        ("activities", "0002_occurrence_place"),
        ("journeys", "0001_initial"),
        ("access", "0001_initial"),
        ("commerce", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="domain_event",
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="core.domaineventoutbox"),
        ),
        migrations.AddField(
            model_name="notification",
            name="activity",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="activities.activity"),
        ),
        migrations.AddField(
            model_name="notification",
            name="journey",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="journeys.journey"),
        ),
        migrations.AddField(
            model_name="notification",
            name="access",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="access.access"),
        ),
        migrations.AddField(
            model_name="notification",
            name="commerce_order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="commerce.commerceorder"),
        ),
        migrations.AddField(
            model_name="notification",
            name="template_key",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["domain_event", "recipient"], name="notif_domain_recipient_idx"),
        ),
    ]

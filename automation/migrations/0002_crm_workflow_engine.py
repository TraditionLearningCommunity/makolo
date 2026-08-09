import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0001_initial"),
        ("crm", "0002_followers_tags_fields_templates_attribution"),
        ("events", "0002_event_organization"),
        ("organizations", "0002_organizationfollow"),
        ("tickets", "0003_ticketwaitlistentry_tickettransfer"),
    ]

    operations = [
        migrations.CreateModel(
            name="CRMWorkflow",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("trigger", models.CharField(choices=[("followed_organizer", "Nouvel abonné organisateur"), ("order_confirmed", "Commande confirmée"), ("order_expired", "Commande expirée"), ("waitlist_joined", "Entrée en liste d’attente"), ("checked_in", "Participant scanné / présent"), ("before_event", "Avant le début d’un événement"), ("event_ended", "Après la fin d’un événement"), ("no_show", "Participant absent / no-show"), ("birthday", "Anniversaire du contact")], max_length=32)),
                ("min_order_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("event_offset_minutes", models.PositiveIntegerField(default=0, help_text="Pour le déclencheur avant événement : nombre de minutes avant le début.", validators=[django.core.validators.MaxValueValidator(525600)])),
                ("trigger_grace_minutes", models.PositiveIntegerField(default=60, help_text="Fenêtre pendant laquelle un déclencheur temporel reste valable.", validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10080)])),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_crm_workflows", to=settings.AUTH_USER_MODEL)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="crm_workflows", to="events.event")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="crm_workflows", to="organizations.organization")),
                ("segment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="automation_workflows", to="crm.audiencesegment")),
                ("ticket_type", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_workflows", to="tickets.tickettype")),
            ],
            options={"ordering": ["organization__name", "name"]},
        ),
        migrations.CreateModel(
            name="CRMWorkflowAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("position", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("kind", models.CharField(choices=[("send_email_template", "Envoyer un modèle e-mail"), ("in_app_notification", "Notification Makolo au contact"), ("add_tag", "Ajouter un tag CRM"), ("remove_tag", "Retirer un tag CRM"), ("notify_team", "Notifier l’équipe organisatrice")], max_length=32)),
                ("delay_minutes", models.PositiveIntegerField(default=0, help_text="Délai après l’étape précédente.", validators=[django.core.validators.MaxValueValidator(525600)])),
                ("title", models.CharField(blank=True, max_length=180)),
                ("message", models.TextField(blank=True)),
                ("marketing_action", models.BooleanField(default=False, help_text="Pour une notification Makolo promotionnelle, exige le consentement marketing et les préférences de l’organisateur.")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tag", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="automation_actions", to="crm.crmtag")),
                ("template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="automation_actions", to="crm.campaigntemplate")),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="automation.crmworkflow")),
            ],
            options={"ordering": ["workflow", "position"]},
        ),
        migrations.CreateModel(
            name="CRMWorkflowRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_type", models.CharField(max_length=40)),
                ("source_id", models.CharField(max_length=255)),
                ("dedup_key", models.CharField(max_length=255, unique=True)),
                ("status", models.CharField(choices=[("waiting", "En attente"), ("running", "En cours"), ("completed", "Terminé"), ("skipped", "Ignoré"), ("failed", "Échoué"), ("cancelled", "Annulé")], default="waiting", max_length=16)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("skip_reason", models.CharField(blank=True, max_length=255)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="automation_runs", to="crm.crmcontact")),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_workflow_runs", to="events.event")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_workflow_runs", to="tickets.ticketorder")),
                ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_workflow_runs", to="tickets.ticket")),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="automation.crmworkflow")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="CRMWorkflowActionRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "En attente"), ("processing", "En cours"), ("completed", "Terminé"), ("skipped", "Ignoré"), ("failed", "Échoué")], default="queued", max_length=16)),
                ("scheduled_for", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("output", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="automation.crmworkflowaction")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="action_runs", to="automation.crmworkflowrun")),
            ],
            options={"ordering": ["scheduled_for", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="crmworkflow",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="crm_workflow_org_name_unique"),
        ),
        migrations.AddIndex(
            model_name="crmworkflow",
            index=models.Index(fields=["organization", "is_active", "trigger"], name="crm_wf_org_trigger_idx"),
        ),
        migrations.AddIndex(
            model_name="crmworkflow",
            index=models.Index(fields=["event", "trigger", "is_active"], name="crm_wf_event_trigger_idx"),
        ),
        migrations.AddConstraint(
            model_name="crmworkflowaction",
            constraint=models.UniqueConstraint(fields=("workflow", "position"), name="crm_workflow_action_position_unique"),
        ),
        migrations.AddIndex(
            model_name="crmworkflowrun",
            index=models.Index(fields=["workflow", "status", "created_at"], name="crm_wf_run_status_idx"),
        ),
        migrations.AddIndex(
            model_name="crmworkflowrun",
            index=models.Index(fields=["contact", "created_at"], name="crm_wf_run_contact_idx"),
        ),
        migrations.AddConstraint(
            model_name="crmworkflowactionrun",
            constraint=models.UniqueConstraint(fields=("run", "action"), name="crm_workflow_action_run_unique"),
        ),
        migrations.AddIndex(
            model_name="crmworkflowactionrun",
            index=models.Index(fields=["status", "scheduled_for"], name="crm_wf_action_due_idx"),
        ),
        migrations.AddIndex(
            model_name="crmworkflowactionrun",
            index=models.Index(fields=["run", "status"], name="crm_wf_action_run_idx"),
        ),
    ]

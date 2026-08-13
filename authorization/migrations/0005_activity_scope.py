import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


SCOPE_CHOICES = [
    ("platform", "Plateforme Makolo"),
    ("space", "Espace"),
    ("group", "Groupe"),
    ("activity", "Activité"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0004_space_places_permissions"),
        ("activities", "0001_initial"),
    ]
    operations = [
        migrations.AlterField(model_name="permission", name="scope_type", field=models.CharField(choices=SCOPE_CHOICES, max_length=16)),
        migrations.AlterField(model_name="role", name="scope_type", field=models.CharField(choices=SCOPE_CHOICES, max_length=16)),
        migrations.AlterField(model_name="mandate", name="scope_type", field=models.CharField(choices=SCOPE_CHOICES, max_length=16)),
        migrations.AddField(
            model_name="mandate",
            name="activity",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="authority_mandates", to="activities.activity"),
        ),
        migrations.AlterModelOptions(
            name="mandate",
            options={"ordering": ["scope_type", "space__name", "group__name", "activity__title", "profile__email", "role__name"]},
        ),
        migrations.RemoveConstraint(model_name="role", name="auth_role_scope_organization_valid"),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scope_type="platform", is_system=True, organization__isnull=True)
                    | Q(scope_type="space", is_system=True, organization__isnull=True)
                    | Q(scope_type="space", is_system=False, organization__isnull=False)
                    | Q(scope_type="group", is_system=True, organization__isnull=True)
                    | Q(scope_type="activity", is_system=True, organization__isnull=True)
                ),
                name="auth_role_scope_organization_valid",
            ),
        ),
        migrations.RemoveConstraint(model_name="mandate", name="auth_mandate_scope_target_valid"),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scope_type="platform", space__isnull=True, group__isnull=True, activity__isnull=True)
                    | Q(scope_type="space", space__isnull=False, group__isnull=True, activity__isnull=True)
                    | Q(scope_type="group", space__isnull=True, group__isnull=False, activity__isnull=True)
                    | Q(scope_type="activity", space__isnull=True, group__isnull=True, activity__isnull=False)
                ),
                name="auth_mandate_scope_target_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(fields=("profile", "role", "scope_type", "activity"), condition=Q(scope_type="activity", status="active"), name="auth_mandate_active_activity_unique"),
        ),
        migrations.AddIndex(model_name="mandate", index=models.Index(fields=["activity", "status"], name="auth_mand_act_status_idx")),
    ]

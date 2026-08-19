from django.db import migrations


def align_space_console_roles(apps, schema_editor):
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    activity_manager = Role.objects.filter(
        code="space-activity-manager",
        scope_type="space",
        is_system=True,
    ).first()
    if activity_manager:
        RolePermission.objects.filter(
            role=activity_manager,
            permission__code__in=(
                "crm.view",
                "crm.manage",
                "promotions.view",
                "promotions.manage",
                "growth.feedback.view",
                "analytics.growth.view",
            ),
        ).delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0010_scanner_operations_permissions")]
    operations = [migrations.RunPython(align_space_console_roles, noop)]

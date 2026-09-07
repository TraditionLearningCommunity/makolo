from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_profile_foundations"),
    ]

    operations = [
        migrations.RemoveField(model_name="user", name="roles"),
        migrations.RemoveField(model_name="user", name="permission_groups"),
        migrations.RemoveField(model_name="user", name="is_organizer"),
        migrations.RemoveField(model_name="user", name="is_scanner_agent"),
        migrations.RemoveIndex(model_name="user", name="accounts_us_is_veri_fa45d6_idx"),
        migrations.RemoveField(model_name="user", name="is_verified"),
        migrations.RemoveField(model_name="user", name="settings_data"),
        migrations.RemoveField(model_name="user", name="analytics_data"),
        migrations.RemoveField(model_name="userprofile", name="profile_completed"),
        migrations.DeleteModel(name="UserActivity"),
        migrations.DeleteModel(name="VerificationDocument"),
        migrations.DeleteModel(name="PermissionGroup"),
        migrations.DeleteModel(name="Role"),
    ]

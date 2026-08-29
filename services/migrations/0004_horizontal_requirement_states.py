from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError


OLD_TO_NEW = {
    "unassessed": "unassessed",
    "satisfied": "satisfied",
    "action_required": "pending",
    "needs_review": "pending",
    "not_applicable": "not_applicable",
    "not_eligible": "unsatisfied",
}


def migrate_requirement_assessment_states(apps, schema_editor):
    Assessment = apps.get_model("services", "ServiceRequirementAssessment")
    alias = schema_editor.connection.alias
    queryset = Assessment.objects.using(alias).all()
    present = set(queryset.values_list("status", flat=True).distinct())
    unknown = present - set(OLD_TO_NEW)
    if unknown:
        raise RuntimeError(
            "Unknown historical ServiceRequirementAssessment states: "
            + ", ".join(sorted(unknown))
        )
    for old_state, new_state in OLD_TO_NEW.items():
        if old_state != new_state:
            queryset.filter(status=old_state).update(status=new_state)


def reverse_requirement_assessment_states(apps, schema_editor):
    raise IrreversibleError(
        "T34A intentionally collapses action_required/needs_review into pending and "
        "not_eligible into unsatisfied; the original pseudo-state cannot be reconstructed honestly."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0003_payments_submissions_outcomes"),
    ]

    operations = [
        migrations.RunPython(
            migrate_requirement_assessment_states,
            reverse_code=reverse_requirement_assessment_states,
        ),
        migrations.AlterField(
            model_name="servicerequirementassessment",
            name="status",
            field=models.CharField(
                choices=[
                    ("unassessed", "Unassessed"),
                    ("pending", "Pending"),
                    ("satisfied", "Satisfied"),
                    ("unsatisfied", "Unsatisfied"),
                    ("not_applicable", "Not applicable"),
                ],
                default="unassessed",
                max_length=20,
            ),
        ),
    ]

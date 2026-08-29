from django.db import migrations, models


OLD_TO_NEW = {
    "unassessed": "unassessed",
    "satisfied": "satisfied",
    "action_required": "pending",
    "needs_review": "pending",
    "not_applicable": "not_applicable",
    "not_eligible": "unsatisfied",
}

# The forward normalization intentionally removes distinctions that cannot be
# reconstructed. Django migration-graph tests still need to move backwards, so
# a downgrade uses one deterministic legacy representative for each collapsed
# state. In particular, former needs_review rows cannot be distinguished from
# former action_required rows after both became pending.
NEW_TO_OLD_LOSSY = {
    "unassessed": "unassessed",
    "pending": "action_required",
    "satisfied": "satisfied",
    "unsatisfied": "not_eligible",
    "not_applicable": "not_applicable",
}


def _normalize_states(*, apps, schema_editor, mapping, label):
    Assessment = apps.get_model("services", "ServiceRequirementAssessment")
    alias = schema_editor.connection.alias
    queryset = Assessment.objects.using(alias).all()
    present = set(queryset.values_list("status", flat=True).distinct())
    unknown = present - set(mapping)
    if unknown:
        raise RuntimeError(
            f"Unknown {label} ServiceRequirementAssessment states: "
            + ", ".join(sorted(unknown))
        )
    for old_state, new_state in mapping.items():
        if old_state != new_state:
            queryset.filter(status=old_state).update(status=new_state)


def migrate_requirement_assessment_states(apps, schema_editor):
    _normalize_states(
        apps=apps,
        schema_editor=schema_editor,
        mapping=OLD_TO_NEW,
        label="historical",
    )


def reverse_requirement_assessment_states(apps, schema_editor):
    _normalize_states(
        apps=apps,
        schema_editor=schema_editor,
        mapping=NEW_TO_OLD_LOSSY,
        label="T34A",
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

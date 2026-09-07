from django.db import migrations


POLICY_CODE = "default-network-utility"
POLICY_VERSION = 1


def align_seed_rules(apps, schema_editor):
    Rule = apps.get_model("recognition", "RecognitionRule")
    base = Rule.objects.filter(policy__code=POLICY_CODE, policy__version=POLICY_VERSION)

    # Journey fulfillment is a terminal state transition: repeated observations
    # of the same fulfilled state must not create new utility.
    base.filter(code="journey-fulfilled").update(
        temporal_profile="transition",
        aggregation="LATEST_STATE",
    )

    # Publishing a new revision and closing another operational checkpoint are
    # distinct useful acts. They are PULSE facts, not a duplicated state value.
    base.filter(code="opportunity-published").update(
        temporal_profile="pulse",
        aggregation="SUM_DISTINCT_OUTCOME",
    )
    base.filter(code="checkpoint-closed").update(
        temporal_profile="pulse",
        aggregation="SUM_DISTINCT_OUTCOME",
    )


def restore_previous_seed_rules(apps, schema_editor):
    Rule = apps.get_model("recognition", "RecognitionRule")
    base = Rule.objects.filter(policy__code=POLICY_CODE, policy__version=POLICY_VERSION)
    base.filter(code="journey-fulfilled").update(
        temporal_profile="transition",
        aggregation="SUM_DISTINCT_OUTCOME",
    )
    base.filter(code="opportunity-published").update(
        temporal_profile="transition",
        aggregation="SUM_DISTINCT_OUTCOME",
    )
    base.filter(code="checkpoint-closed").update(
        temporal_profile="transition",
        aggregation="SUM_DISTINCT_OUTCOME",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0003_object_pool_temporal_pending"),
    ]

    operations = [
        migrations.RunPython(align_seed_rules, restore_previous_seed_rules),
    ]

from django.db import migrations, models


CHANNEL_CHOICES = [
    ("capacity", "Capacity"),
    ("coverage", "Coverage"),
    ("actionability", "Actionability"),
    ("real_action", "Real Action"),
    ("economic", "Economic"),
    ("reliability", "Reliability"),
    ("durability", "Durability"),
    ("promotional", "Promotional"),
    ("utility", "Utility"),
]


def align_default_temporal_rules(apps, schema_editor):
    Policy = apps.get_model("recognition", "RecognitionPolicy")
    Rule = apps.get_model("recognition", "RecognitionRule")
    policy = Policy.objects.filter(code="default-network-utility", version=1).first()
    if policy is None:
        return
    Rule.objects.filter(policy=policy, code__in=["journey-fulfilled", "opportunity-published"]).update(
        aggregation="LATEST_STATE"
    )
    # Each operational checkpoint closure is its own observed transition/outcome.
    Rule.objects.filter(policy=policy, code="checkpoint-closed").update(temporal_profile="pulse")


class Migration(migrations.Migration):
    dependencies = [("recognition", "0002_policy_signals_economy")]

    operations = [
        migrations.AlterField(
            model_name="recognitionaccrual",
            name="channel",
            field=models.CharField(choices=CHANNEL_CHOICES, max_length=24),
        ),
        migrations.AlterField(
            model_name="recognitionrule",
            name="channel",
            field=models.CharField(choices=CHANNEL_CHOICES, default="actionability", max_length=24),
        ),
        migrations.AlterField(
            model_name="recognitionslicereceipt",
            name="channel",
            field=models.CharField(choices=CHANNEL_CHOICES, max_length=24),
        ),
        migrations.AlterField(
            model_name="recognitionledgerentry",
            name="kind",
            field=models.CharField(
                choices=[
                    ("grant", "Grant"),
                    ("pending", "Pending"),
                    ("spend", "Spend"),
                    ("reversal", "Reversal"),
                    ("adjustment", "Adjustment"),
                ],
                max_length=16,
            ),
        ),
        migrations.RunPython(align_default_temporal_rules, migrations.RunPython.noop),
    ]

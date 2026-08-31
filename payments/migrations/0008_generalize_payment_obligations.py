from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_profilefollow"),
        ("payments", "0007_payment_obligation_commerce_order_set_null"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentobligation",
            name="journey",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payment_obligations",
                to="journeys.journey",
            ),
        ),
        migrations.AlterField(
            model_name="paymentobligation",
            name="reason",
            field=models.CharField(
                choices=[
                    ("commerce", "Commerce"),
                    ("subscription", "Subscription"),
                    ("opportunity_requirement", "Requirement Opportunity"),
                    ("service_process", "Processus Service"),
                    ("access_requirement", "Condition d’accès"),
                    ("other", "Autre"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="paymentobligation",
            name="payer_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payer_payment_obligations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="paymentobligation",
            name="payer_space",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payer_payment_obligations",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="paymentobligation",
            name="payee_platform",
            field=models.BooleanField(default=False),
        ),
        migrations.RemoveConstraint(
            model_name="paymentobligation",
            name="payobl_exactly_one_payee",
        ),
        migrations.AddConstraint(
            model_name="paymentobligation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        payee_space__isnull=False,
                        payee_profile__isnull=True,
                        payee_platform=False,
                        external_payee_name="",
                    )
                    | models.Q(
                        payee_space__isnull=True,
                        payee_profile__isnull=False,
                        payee_platform=False,
                        external_payee_name="",
                    )
                    | models.Q(
                        payee_space__isnull=True,
                        payee_profile__isnull=True,
                        payee_platform=True,
                        external_payee_name="",
                    )
                    | (
                        models.Q(
                            payee_space__isnull=True,
                            payee_profile__isnull=True,
                            payee_platform=False,
                        )
                        & ~models.Q(external_payee_name="")
                    )
                ),
                name="payobl_exactly_one_payee",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentobligation",
            constraint=models.CheckConstraint(
                condition=models.Q(payer_space__isnull=True) | models.Q(payer_profile__isnull=True),
                name="payobl_payer_not_multiple",
            ),
        ),
    ]

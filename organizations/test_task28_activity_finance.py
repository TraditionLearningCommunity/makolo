from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from commerce.models import CommerceOrder, PaymentMode
from journeys.models import Journey, WorkflowKind
from payments.models import Payment

from .console_context import SpaceConsoleContext
from .console_selectors import payments_for_console
from .services import create_organization


User = get_user_model()


class Task28ActivityFinanceConsoleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="task28-finance-owner",
            email="task28-finance-owner@example.test",
            password="StrongPass2026!",
        )
        self.local_finance = User.objects.create_user(
            username="task28-local-finance",
            email="task28-local-finance@example.test",
            password="StrongPass2026!",
        )
        self.space = create_organization(creator=self.owner, name="Task 28 Finance Scope")
        self.activity_a = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Activity Finance A",
        )
        self.activity_b = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Activity Scanner B",
        )
        grant_activity_role(
            profile=self.local_finance,
            activity=self.activity_a,
            role=SystemRoleCode.ACTIVITY_FINANCE,
            granted_by=self.owner,
        )
        # Deliberately add a different local role on B. The Console context will
        # contain both Activity ids, so payment scoping must be permission-specific.
        grant_activity_role(
            profile=self.local_finance,
            activity=self.activity_b,
            role=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
        )
        self.payment_a = self._payment_for(self.activity_a, "A")
        self.payment_b = self._payment_for(self.activity_b, "B")

    def _payment_for(self, activity, suffix):
        journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=activity,
            workflow=WorkflowKind.PURCHASE,
        )
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.owner,
            payee_space=self.space,
            payment_mode=PaymentMode.UPFRONT,
            subtotal=Decimal("10.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("10.00"),
            currency="USD",
            source_key=f"task28-finance-{suffix}",
        )
        return Payment.objects.create(
            commerce_order=order,
            initiated_by=self.owner,
            amount=Decimal("10.00"),
            currency="USD",
        )

    def test_activity_finance_sees_payments_module_but_only_for_finance_activity(self):
        context = SpaceConsoleContext.build(self.local_finance, self.space)
        self.assertIsNotNone(context)
        self.assertTrue(context.limited_to_activities)
        self.assertEqual(set(context.activity_ids), {self.activity_a.pk, self.activity_b.pk})
        visible = {
            item["key"]
            for group in context.navigation_groups
            for item in group["items"]
        }
        self.assertIn("payments", visible)
        self.assertNotIn("team", visible)
        self.assertNotIn("settings", visible)

        payment_ids = set(payments_for_console(context).values_list("pk", flat=True))
        self.assertEqual(payment_ids, {self.payment_a.pk})
        self.assertNotIn(self.payment_b.pk, payment_ids)

    def test_direct_payments_route_does_not_expose_other_activity(self):
        self.client.force_login(self.local_finance)
        response = self.client.get(
            reverse("organizations:console-payments", kwargs={"slug": self.space.slug})
        )
        self.assertEqual(response.status_code, 200)
        page_ids = {payment.pk for payment in response.context["page_obj"].object_list}
        self.assertEqual(page_ids, {self.payment_a.pk})

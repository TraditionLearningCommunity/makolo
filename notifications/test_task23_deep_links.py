from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access.services import issue_access
from activities.models import Activity
from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import Notification, NotificationCategory, NotificationKind


User = get_user_model()


class NotificationDeepLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="task23-notification-user",
            email="task23-notification@example.com",
            password="Task23-2026!",
        )
        self.other = User.objects.create_user(
            username="task23-notification-other",
            email="task23-notification-other@example.com",
            password="Task23-2026!",
        )
        self.activity = Activity.objects.create(created_by=self.user, title="Task 23 deep link")
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.PENDING_PAYMENT,
        )

    def notification(self, **kwargs):
        defaults = {
            "recipient": self.user,
            "kind": NotificationKind.SYSTEM,
            "category": NotificationCategory.SYSTEM,
            "title": "Task 23",
            "message": "Ouvrir la cible exacte.",
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def test_access_notification_opens_exact_access(self):
        access = issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=None,
            journey=self.journey,
            source_key="task23:notification-access",
        )
        notification = self.notification(access=access, journey=self.journey, template_key="access.issued")
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertRedirects(
            response,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
            fetch_redirect_response=False,
        )

    def test_journey_notification_opens_exact_journey(self):
        notification = self.notification(journey=self.journey, template_key="journey.confirmed")
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertRedirects(
            response,
            reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}),
            fetch_redirect_response=False,
        )

    def test_payment_required_notification_opens_exact_commerce_order_payment_route(self):
        order = CommerceOrder.objects.create(
            journey=self.journey,
            buyer=self.user,
            status=CommerceOrderStatus.PENDING,
            payment_mode=PaymentMode.AFTER_APPROVAL,
            subtotal=Decimal("15.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("15.00"),
            currency="USD",
        )
        notification = self.notification(
            journey=self.journey,
            commerce_order=order,
            template_key="journey.payment.required",
            category=NotificationCategory.PAYMENT,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertRedirects(
            response,
            reverse("payments:commerce-start", kwargs={"order_pk": order.pk}),
            fetch_redirect_response=False,
        )

    def test_notification_uuid_of_another_participant_is_not_readable(self):
        foreign = Notification.objects.create(
            recipient=self.other,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SYSTEM,
            title="Foreign",
            message="Private",
            journey=self.journey,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": foreign.pk}))
        self.assertEqual(response.status_code, 404)

    def test_missing_relational_target_falls_back_to_notifications_list(self):
        access = issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=None,
            source_key="task23:notification-deleted",
        )
        notification = self.notification(
            access=access,
            template_key="access.issued",
            action_url=f"/me/accesses/{access.pk}/",
        )
        notification.access = None
        notification.save(update_fields=["access", "updated_at"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:open", kwargs={"pk": notification.pk}))
        self.assertRedirects(
            response,
            f"/me/accesses/{access.pk}/",
            fetch_redirect_response=False,
        )

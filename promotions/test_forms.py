from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from crm.canonical_models import Audience
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization
from tickets.models import TicketType

from .forms import PromotionForm


User = get_user_model()


class PromotionFormTests(TestCase):
    def test_create_form_validates_event_and_audience_with_canonical_space(self):
        owner = User.objects.create_user(username="promo-form-owner", email="promo-form-owner@test.invalid")
        space = Organization.objects.create(name="Promotion Form Space", created_by=owner)
        event = Event.objects.create(
            organizer=owner,
            organization=space,
            title="Promotion Form Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=2),
            published_at=timezone.now(),
            capacity=20,
        )
        ticket_type = TicketType.objects.create(
            event=event,
            name="Pass standard",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=20,
        )
        audience = Audience.objects.create(
            organization=space,
            name="Audience test",
            created_by=owner,
        )

        form = PromotionForm(
            organization=space,
            data={
                "name": "Promotion test",
                "description": "",
                "event": str(event.pk),
                "discount_type": "percent",
                "discount_value": "15.00",
                "max_discount_amount": "",
                "min_order_amount": "0.00",
                "currency": "USD",
                "eligible_ticket_types": [str(ticket_type.pk)],
                "starts_at": "",
                "ends_at": "",
                "max_redemptions": "",
                "max_redemptions_per_customer": "1",
                "is_active": "on",
                "audience": str(audience.pk),
            },
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.instance.organization_id, space.pk)
        self.assertEqual(form.cleaned_data["event"].pk, event.pk)
        self.assertEqual(form.cleaned_data["audience"].pk, audience.pk)

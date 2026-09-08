from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import ActivityStatus, ActivityVisibility
from core.product_language import vertical_for, vocabulary_for

from .services import create_funding


User = get_user_model()


class FundingDiscoveryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="funding-discovery@example.test", username="funding-discovery", password="test-pass")
        self.funding = create_funding(
            actor=self.owner,
            title="Financer une bibliothèque mobile",
            short_description="Réunir les moyens du premier trajet.",
            currency="USD",
            target_amount=Decimal("500.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def test_funding_uses_contextual_product_language(self):
        self.assertEqual(vertical_for(self.funding.activity), "funding")
        vocabulary = vocabulary_for(activity=self.funding.activity)
        self.assertEqual(vocabulary.activity_noun, "Financement")
        self.assertEqual(vocabulary.primary_action, "Contribuer")

    def test_funding_is_a_discovery_candidate(self):
        response = self.client.get(reverse("discovery:home"), {"vertical": "funding"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financer une bibliothèque mobile")
        self.assertContains(response, "Contribuer")
        self.assertContains(response, "Reste : 500.00 USD")

    def test_funding_does_not_claim_place_filter_it_cannot_prove(self):
        response = self.client.get(reverse("discovery:home"), {"vertical": "funding", "place": "Kolwezi"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Financer une bibliothèque mobile")

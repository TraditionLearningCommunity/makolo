from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from discovery.candidate_capabilities import requested_filter_keys
from discovery.intent import AppliedConstraint, ConstraintSource
from services.models import ServiceDetails, ServiceKind


class UnifiedDiscoveryServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="discover-owner",
            email="discover-owner@example.test",
            password="test-password",
        )
        self.public_activity = Activity.objects.create(
            owner_profile=self.owner,
            title="Accompagnement études internationales",
            short_description="Préparer un dossier et avancer étape par étape.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.service = ServiceDetails.objects.create(
            activity=self.public_activity,
            service_kind=ServiceKind.EDUCATION_GUIDANCE,
        )
        private_activity = Activity.objects.create(
            owner_profile=self.owner,
            title="Accompagnement privé invisible",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ServiceDetails.objects.create(
            activity=private_activity,
            service_kind=ServiceKind.OTHER,
        )

    def test_discover_includes_public_accompaniment_and_respects_visibility(self):
        response = self.client.get(reverse("discovery:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accompagnement études internationales")
        self.assertContains(response, "Accompagnement")
        self.assertNotContains(response, "Accompagnement privé invisible")

    def test_transverse_search_matches_service_activity_text(self):
        response = self.client.get(reverse("discovery:home"), {"q": "internationales"})

        self.assertContains(response, "Accompagnement études internationales")
        self.assertEqual(response.context["result_count"], 1)

    def test_category_filter_exposes_user_intents_not_backend_products(self):
        service_response = self.client.get(reverse("discovery:home"), {"vertical": "service"})
        event_response = self.client.get(reverse("discovery:home"), {"vertical": "event"})

        self.assertContains(service_response, "Être accompagné")
        self.assertContains(service_response, "Accompagnement études internationales")
        self.assertNotContains(event_response, "Accompagnement études internationales")
        self.assertNotContains(service_response, '<option value="opportunity"', html=False)

    def test_service_result_links_to_existing_service_intake_route(self):
        response = self.client.get(reverse("discovery:home"), {"vertical": "service"})

        self.assertContains(response, reverse("services:start", kwargs={"pk": self.service.pk}))

    def test_general_search_does_not_inject_service_for_unsupported_filters(self):
        cases = (
            {"place": "Lubumbashi"},
            {"when": "tomorrow"},
            {"date": "2026-09-06"},
            {"date_from": "2026-09-06", "date_to": "2026-09-10"},
            {"price": "free"},
            {"lat": "-11.6647", "lon": "27.4794", "radius_km": "10"},
        )
        for params in cases:
            with self.subTest(params=params):
                response = self.client.get(reverse("discovery:home"), params)
                self.assertNotContains(response, "Accompagnement études internationales")

    def test_explicit_service_filter_without_unsupported_constraint_keeps_service(self):
        response = self.client.get(reverse("discovery:home"), {"vertical": "service"})
        self.assertContains(response, "Accompagnement études internationales")
        self.assertEqual(response.context["result_count"], 1)

    def test_internal_default_constraint_is_not_treated_as_requested_filter(self):
        requested = requested_filter_keys(
            requested_params={},
            constraints=(
                AppliedConstraint("ordering", "soon", "Bientôt", ConstraintSource.DEFAULT),
            ),
        )
        self.assertNotIn("ordering", requested)

    def test_interpreted_constraint_is_treated_as_requested_filter(self):
        requested = requested_filter_keys(
            requested_params={"q": "demain"},
            constraints=(
                AppliedConstraint("when", "tomorrow", "Demain", ConstraintSource.INTERPRETED),
            ),
        )
        self.assertIn("when", requested)

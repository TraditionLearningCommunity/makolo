from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.models import Journey
from objectives.models import Dossier
from services.models import ServiceDetails, ServiceKind

from .models import DiscoveryWatch, DiscoveryWatchStatus
from .watches import execute_watch, normalize_watch_criteria


User = get_user_model()


class DiscoveryWatchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="watch-owner",
            email="watch-owner@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="watch-other",
            email="watch-other@example.test",
            password="StrongPass2026!",
        )
        service_activity = Activity.objects.create(
            owner_profile=self.owner,
            title="Accompagnement Watch",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        ServiceDetails.objects.create(
            activity=service_activity,
            service_kind=ServiceKind.ORIENTATION,
        )

    def test_valid_watch_is_created_and_empty_criteria_are_rejected(self):
        before_dossiers = Dossier.objects.count()
        before_journeys = Journey.objects.count()
        watch = DiscoveryWatch.objects.create(owner=self.owner, name="Bourses", criteria={"q": "bourse"})
        self.assertEqual(watch.criteria, {"q": "bourse"})
        self.assertEqual(Dossier.objects.count(), before_dossiers)
        self.assertEqual(Journey.objects.count(), before_journeys)
        with self.assertRaises(ValidationError):
            DiscoveryWatch.objects.create(owner=self.owner, name="Bloc-notes", criteria={})

    def test_owner_isolation_and_private_routes(self):
        watch = DiscoveryWatch.objects.create(owner=self.owner, name="Canada", criteria={"q": "Canada"})
        self.client.force_login(self.other)
        response = self.client.get(reverse("discovery:watch-list"))
        self.assertNotContains(response, "Canada")
        self.assertEqual(self.client.get(reverse("discovery:watch-detail", args=[watch.id])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("discovery:watch-list")).status_code, 302)

    def test_pause_reactivate_and_modify(self):
        watch = DiscoveryWatch.objects.create(owner=self.owner, name="Canada", criteria={"q": "Canada"})
        self.client.force_login(self.owner)
        self.client.post(reverse("discovery:watch-status", args=[watch.id]), {"action": "pause"})
        watch.refresh_from_db()
        self.assertEqual(watch.status, DiscoveryWatchStatus.PAUSED)
        self.client.post(reverse("discovery:watch-status", args=[watch.id]), {"action": "activate"})
        watch.refresh_from_db()
        self.assertEqual(watch.status, DiscoveryWatchStatus.ACTIVE)
        response = self.client.post(
            reverse("discovery:watch-edit", args=[watch.id]),
            {"name": "Canada 2027", "q": "bourse master", "when": "", "period": "", "vertical": "", "price": "", "radius_km": "", "ordering": "", "place": "", "date": "", "date_from": "", "date_to": "", "lat": "", "lon": "", "timezone": "", "dossier": ""},
        )
        self.assertEqual(response.status_code, 302)
        watch.refresh_from_db()
        self.assertEqual(watch.name, "Canada 2027")
        self.assertEqual(watch.criteria, {"q": "bourse master"})

    def test_optional_dossier_must_belong_to_same_owner(self):
        own = Dossier.objects.create(title="Étudier au Canada", created_by=self.owner, owner_profile=self.owner)
        foreign = Dossier.objects.create(title="Privé tiers", created_by=self.other, owner_profile=self.other)
        watch = DiscoveryWatch.objects.create(owner=self.owner, name="Bourses", criteria={"q": "bourse"}, dossier=own)
        self.assertEqual(watch.dossier, own)
        with self.assertRaises(ValidationError):
            DiscoveryWatch.objects.create(owner=self.owner, name="Interdit", criteria={"q": "visa"}, dossier=foreign)

    def test_service_watch_rejects_filters_discovery_does_not_execute(self):
        cases = (
            {"vertical": "service", "place": "Lubumbashi"},
            {"vertical": "service", "when": "tomorrow"},
            {"vertical": "service", "date": "2026-09-06"},
            {"vertical": "service", "price": "free"},
            {"vertical": "service", "lat": "-11.6647", "lon": "27.4794", "radius_km": "10"},
        )
        for criteria in cases:
            with self.subTest(criteria=criteria), self.assertRaises(ValidationError):
                normalize_watch_criteria(criteria)

    def test_general_watch_does_not_inject_service_when_family_cannot_prove_filter(self):
        cases = (
            {"place": "Lubumbashi"},
            {"when": "tomorrow"},
            {"date": "2026-09-06"},
            {"price": "free"},
            {"lat": "-11.6647", "lon": "27.4794", "radius_km": "10"},
        )
        for criteria in cases:
            with self.subTest(criteria=criteria):
                result = execute_watch(criteria, profile=self.owner)
                self.assertEqual(result.service_items, [])

    def test_service_only_watch_remains_executable(self):
        result = execute_watch({"vertical": "service"}, profile=self.owner)
        self.assertEqual(len(result.service_items), 1)
        self.assertEqual(result.service_items[0]["title"], "Accompagnement Watch")

    @patch("discovery.watches.public_service_discovery_items", return_value=[])
    @patch("discovery.watches.search_occurrences")
    def test_replay_delegates_to_canonical_discovery_search(self, search, services):
        search.return_value.items = []
        search.return_value.total = 0
        search.return_value.timezone_name = "Africa/Lubumbashi"
        search.return_value.nearby_active = False
        result = execute_watch({"q": "concert", "vertical": "event"}, profile=self.owner)
        search.assert_called_once_with({"q": "concert", "vertical": "event"}, profile=self.owner, now=None)
        services.assert_called_once_with(
            {"q": "concert", "vertical": "event"},
            profile=self.owner,
            requested_params={"q": "concert", "vertical": "event"},
        )
        self.assertEqual(result.total, 0)

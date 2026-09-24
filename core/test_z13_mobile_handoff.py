from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from accounts.api.views import MeAPIView as AuthMeAPIView
from core.api.day_of_views import PersonalOccurrenceDayOfAPIView
from core.api.detail_views import PersonalJourneyDetailAPIView
from core.api.mark_views import PersonalMarkAPIView
from core.api.me_views import PersonalMeAPIView
from core.api.personal_views import PersonalNowAPIView, PersonalOngoingAPIView
from core.api.projections import PROJECTION_SCHEMA_VERSION
from discovery.api.views import DiscoveryItemsAPIView
from operations.live_api import OccurrenceLiveAPIView


class Z13MobileHandoffRouteContractTests(SimpleTestCase):
    def assert_view(self, path, expected_view):
        match = resolve(path)
        self.assertIs(match.func.view_class, expected_view)

    def test_auth_bootstrap_and_mature_me_are_distinct_contracts(self):
        self.assert_view("/api/v1/accounts/auth/me/", AuthMeAPIView)
        self.assert_view("/api/v1/me/", PersonalMeAPIView)

    def test_primary_mature_mobile_surfaces_resolve_without_parallel_namespace(self):
        self.assert_view("/api/v1/me/now/", PersonalNowAPIView)
        self.assert_view("/api/v1/discovery/items/", DiscoveryItemsAPIView)
        self.assert_view("/api/v1/me/mark/", PersonalMarkAPIView)
        self.assert_view("/api/v1/me/ongoing/", PersonalOngoingAPIView)

        with self.assertRaises(Resolver404):
            resolve("/api/v1/mobile/now/")

    def test_engaged_depths_keep_owner_handoffs(self):
        resource_id = uuid4()
        self.assert_view(
            f"/api/v1/me/journeys/{resource_id}/",
            PersonalJourneyDetailAPIView,
        )
        self.assert_view(
            f"/api/v1/me/occurrences/{resource_id}/day-of/",
            PersonalOccurrenceDayOfAPIView,
        )
        self.assert_view(
            f"/api/v1/operations/occurrences/{resource_id}/live/",
            OccurrenceLiveAPIView,
        )

    def test_mature_projection_schema_remains_v1(self):
        self.assertEqual(PROJECTION_SCHEMA_VERSION, 1)

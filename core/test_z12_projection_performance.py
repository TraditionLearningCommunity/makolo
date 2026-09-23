from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from activities.models import Activity
from core.api.access_projection import (
    ACCESS_RELATION_BENEFICIARY,
    ACCESS_RELATION_PURCHASED_FOR_OTHER,
    build_personal_accesses_data,
)
from core.api.me_projection import build_personal_resources_data
from core.api.personal_projections import ONGOING_LIMIT, build_personal_ongoing_projection
from journeys.models import Journey, JourneyStatus, WorkflowKind
from personal_assets.models import PersonalAssetVersion
from personal_assets.services import create_personal_asset


User = get_user_model()


class Z12ProjectionPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="z12-user",
            email="z12-user@example.test",
            password="Strong-Z12-Password-2026!",
        )
        self.other = User.objects.create_user(
            username="z12-other",
            email="z12-other@example.test",
            password="Strong-Z12-Password-2026!",
        )
        self.activity = Activity.objects.create(
            created_by=self.other,
            owner_profile=self.other,
            title="Activity Z12",
        )

    def _journeys(self, count):
        for index in range(count):
            Journey.objects.create(
                initiated_by=self.user,
                beneficiary=self.user,
                activity=self.activity,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.APPROVED,
            )

    def test_ongoing_stops_after_the_first_family_fills_response_budget(self):
        self._journeys(ONGOING_LIMIT + 12)
        with patch(
            "core.api.personal_projections.participant_active_accesses",
            side_effect=AssertionError("Access must not be queried after the response is full."),
        ), patch(
            "core.api.personal_projections.dossiers_for_profile",
            side_effect=AssertionError("Dossier must not be queried after the response is full."),
        ), patch(
            "core.api.personal_projections.projects_for_profile",
            side_effect=AssertionError("Project must not be queried after the response is full."),
        ):
            data = build_personal_ongoing_projection(self.user)
        self.assertEqual(len(data["items"]), ONGOING_LIMIT)
        self.assertTrue(all(row["kind"] == "journey" for row in data["items"]))

    def _access(self, *, beneficiary, index):
        access = Access.objects.create(
            beneficiary=beneficiary,
            activity=self.activity,
            status=AccessStatus.VALID,
            source_key=f"z12-access-{beneficiary.pk}-{index}",
        )
        AccessCredential.objects.create(access=access)
        return access

    def _access_query_count(self, count):
        for index in range(count):
            self._access(beneficiary=self.user, index=index)
        with CaptureQueriesContext(connection) as queries:
            data = build_personal_accesses_data(
                self.user,
                observed_at=timezone.now(),
                relationship=ACCESS_RELATION_BENEFICIARY,
                limit=50,
            )
        self.assertEqual(len(data["items"]), count)
        return len(queries)

    def test_access_collection_query_growth_is_constant_across_rows(self):
        one = self._access_query_count(1)
        Access.objects.filter(beneficiary=self.user).delete()
        many = self._access_query_count(20)
        self.assertLessEqual(many, one + 1)

    def test_buyer_collection_does_not_load_beneficiary_credentials(self):
        journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.other,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.APPROVED,
        )
        from commerce.models import CommerceOrder

        CommerceOrder.objects.create(
            buyer=self.user,
            journey=journey,
            status="pending",
        )
        access = Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            journey=journey,
            status=AccessStatus.VALID,
            source_key="z12-buyer-access",
        )
        AccessCredential.objects.create(access=access)
        with CaptureQueriesContext(connection) as queries:
            data = build_personal_accesses_data(
                self.user,
                observed_at=timezone.now(),
                relationship=ACCESS_RELATION_PURCHASED_FOR_OTHER,
                limit=50,
            )
        self.assertEqual(data["items"][0]["credential"], None)
        sql = "\n".join(query["sql"].lower() for query in queries.captured_queries)
        self.assertNotIn("access_accesscredential", sql)

    def _resource_query_count(self, count):
        for index in range(count):
            asset = create_personal_asset(
                controller=self.user,
                subject_profile=self.user,
                title=f"Document Z12 {index}",
                kind="other",
            )
            for version in range(1, 4):
                PersonalAssetVersion.objects.create(
                    asset=asset,
                    version=version,
                    file=f"z12/{index}/{version}.pdf",
                    mime_type="application/pdf",
                    size=100,
                    content_hash=f"{index:04d}{version:02d}".ljust(64, "0"),
                    created_by=self.user,
                )
        with CaptureQueriesContext(connection) as queries:
            data = build_personal_resources_data(self.user, limit=6)
        self.assertLessEqual(len(data["documents"]["items"]), 6)
        return len(queries)

    def test_me_resource_preview_does_not_scale_with_asset_versions(self):
        one = self._resource_query_count(1)
        from personal_assets.models import PersonalAsset

        PersonalAsset.objects.filter(controller=self.user).delete()
        many = self._resource_query_count(20)
        self.assertLessEqual(many, one + 2)

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from core.api.access_projection import (
    ACCESS_RELATION_BENEFICIARY,
    ACCESS_RELATION_PURCHASED_FOR_OTHER,
    build_personal_accesses_data,
)
from core.api.me_projection import build_personal_resources_data
from core.api.personal_projections import ONGOING_LIMIT, build_personal_ongoing_projection
from journeys.models import Journey, JourneyStatus, WorkflowKind
from objectives.models import DossierJourneyLink
from objectives.services import create_dossier
from personal_assets.services import create_personal_asset, create_personal_asset_version


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
            "core.api.personal_projections.owned_dossiers_for_profile",
            side_effect=AssertionError("Dossier must not be queried after the response is full."),
        ), patch(
            "core.api.personal_projections.owned_projects_for_profile",
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
        self.assertIsNone(data["items"][0]["credential"])
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
                create_personal_asset_version(
                    actor=self.user,
                    asset=asset,
                    uploaded_file=SimpleUploadedFile(
                        f"z12-{index}-{version}.pdf",
                        (f"%PDF-1.4\nz12-{index}-{version}\n%%EOF\n").encode("utf-8"),
                        content_type="application/pdf",
                    ),
                )
        with CaptureQueriesContext(connection) as queries:
            data = build_personal_resources_data(self.user, limit=6)
        self.assertLessEqual(len(data["documents"]["items"]), 6)
        return len(queries)

    def test_me_resource_preview_does_not_scale_with_asset_versions(self):
        one = self._resource_query_count(1)
        many = self._resource_query_count(20)
        self.assertLessEqual(many, one + 2)


    def _dossiers(self, count):
        for index in range(count):
            dossier = create_dossier(
                actor=self.user,
                owner_profile=self.user,
                title=f"Dossier Z12 {index}",
            )
            journey = Journey.objects.create(
                initiated_by=self.user,
                beneficiary=self.other,
                activity=self.activity,
                workflow=WorkflowKind.REGISTRATION,
                status=JourneyStatus.APPROVED,
            )
            DossierJourneyLink.objects.create(
                dossier=dossier,
                journey=journey,
                linked_by=self.user,
            )

    def test_ongoing_dossier_readiness_query_growth_is_batched(self):
        self._dossiers(2)
        with CaptureQueriesContext(connection) as small:
            small_data = build_personal_ongoing_projection(self.user)
        self.assertEqual(
            len([row for row in small_data["items"] if row["kind"] == "dossier"]),
            2,
        )

        self._dossiers(8)
        with CaptureQueriesContext(connection) as larger:
            larger_data = build_personal_ongoing_projection(self.user)
        self.assertEqual(
            len([row for row in larger_data["items"] if row["kind"] == "dossier"]),
            10,
        )
        self.assertLessEqual(len(larger), len(small) + 2)

    def test_ongoing_access_does_not_load_deep_generic_prefetches(self):
        for index in range(ONGOING_LIMIT):
            self._access(beneficiary=self.user, index=100 + index)
        with CaptureQueriesContext(connection) as queries:
            data = build_personal_ongoing_projection(
                self.user,
                observed_at=timezone.now(),
            )
        self.assertEqual(len(data["items"]), ONGOING_LIMIT)
        self.assertTrue(all(row["kind"] == "access" for row in data["items"]))
        sql = "\n".join(
            query["sql"].lower()
            for query in queries.captured_queries
        )
        self.assertNotIn("access_accesscredential", sql)
        self.assertNotIn("access_accessuse", sql)

    def test_details_check_live_capability_without_building_operations_live(self):
        observed_at = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            status=OccurrenceStatus.SCHEDULED,
            start_at=observed_at,
            end_at=observed_at + timedelta(hours=1),
        )
        journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.APPROVED,
        )
        self.client.force_login(self.user)
        with patch(
            "operations.participant_occurrence_live.resolve_operational_readiness",
            side_effect=AssertionError(
                "Detail capability must not build Operations Live."
            ),
        ):
            journey_response = self.client.get(
                f"/api/v1/me/journeys/{journey.pk}/"
            )
            occurrence_response = self.client.get(
                f"/api/v1/occurrences/{occurrence.pk}/"
            )
        self.assertEqual(journey_response.status_code, 200)
        self.assertEqual(occurrence_response.status_code, 200)
        self.assertIn("live", journey_response.json()["data"]["links"])
        self.assertIn("live", occurrence_response.json()["data"]["links"])


    def test_activity_detail_occurrences_are_server_bounded(self):
        activity = Activity.objects.create(
            created_by=self.user,
            owner_profile=self.user,
            title="Activity Z12 bounded occurrences",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        observed_at = timezone.now()
        for index in range(55):
            Occurrence.objects.create(
                activity=activity,
                label=f"Occurrence {index:02d}",
                status=OccurrenceStatus.SCHEDULED,
                start_at=observed_at,
                end_at=observed_at + timedelta(hours=1),
            )
        self.client.force_login(self.user)
        response = self.client.get(f"/api/v1/activities/{activity.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(len(data["occurrences"]), 50)
        self.assertEqual(data["occurrences_page"]["limit"], 50)
        self.assertTrue(data["occurrences_page"]["has_more"])

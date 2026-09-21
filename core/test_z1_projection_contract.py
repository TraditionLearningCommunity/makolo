from datetime import datetime

from django.test import SimpleTestCase
from django.utils import timezone

from core.api.projections import (
    PERSONAL_PROJECTION_SCOPE,
    PROJECTION_SCHEMA_VERSION,
    ProjectionContractError,
    projection_envelope,
    projection_meta,
)


class UXProjectionContractTests(SimpleTestCase):
    def test_projection_envelope_has_stable_transport_metadata(self):
        observed_at = datetime(
            2026,
            9,
            20,
            17,
            30,
            tzinfo=timezone.get_current_timezone(),
        )

        payload = projection_envelope(
            projection="personal.now",
            generated_at=observed_at,
            data={"items": []},
        )

        self.assertEqual(
            payload,
            {
                "meta": {
                    "projection": "personal.now",
                    "schema_version": PROJECTION_SCHEMA_VERSION,
                    "generated_at": observed_at.isoformat(),
                    "scope": PERSONAL_PROJECTION_SCOPE,
                },
                "data": {"items": []},
            },
        )

    def test_empty_null_and_explicit_unknown_survive_without_reinterpretation(self):
        data = {
            "items": [],
            "primary": None,
            "location": {
                "state": "unknown",
                "reason": "not_observed",
            },
        }

        payload = projection_envelope(projection="personal.me", data=data)

        self.assertEqual(payload["data"], data)
        self.assertIsNone(payload["data"]["primary"])
        self.assertEqual(payload["data"]["items"], [])
        self.assertEqual(payload["data"]["location"]["state"], "unknown")

    def test_projection_metadata_rejects_naive_time(self):
        with self.assertRaises(ProjectionContractError):
            projection_meta(
                projection="personal.now",
                generated_at=datetime(2026, 9, 20, 17, 30),
            )

    def test_projection_contract_rejects_invalid_transport_codes_and_versions(self):
        for projection in ("", "Personal Now", "personal/now"):
            with self.subTest(projection=projection):
                with self.assertRaises(ProjectionContractError):
                    projection_meta(projection=projection)

        with self.assertRaises(ProjectionContractError):
            projection_meta(projection="personal.now", scope="Personal")

        for version in (0, -1, True, "1"):
            with self.subTest(version=version):
                with self.assertRaises(ProjectionContractError):
                    projection_meta(
                        projection="personal.now",
                        schema_version=version,
                    )

    def test_projection_data_must_remain_an_object_not_a_bare_collection(self):
        with self.assertRaises(ProjectionContractError):
            projection_envelope(
                projection="personal.ongoing",
                data=[],
            )

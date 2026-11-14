"""Ongoing N1 server pagination: bounded, viewer-bound and terminal only at end."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import SimpleTestCase
from django.utils import timezone

from core.api.personal_projections import (
    ONGOING_LIMIT,
    ONGOING_CONTINUATION_SALT,
    build_personal_ongoing_projection,
    ongoing_continuation_offset,
)
from core.read_models.personal_ongoing import PersonalOngoingEntry


class OngoingContinuationTests(SimpleTestCase):
    def setUp(self):
        self.profile = SimpleNamespace(pk=uuid4())
        self.other = SimpleNamespace(pk=uuid4())

    def _projection(self, *, total=ONGOING_LIMIT * 2 + 3, offset=0):
        entries = [
            PersonalOngoingEntry(
                kind="project", value=SimpleNamespace(number=i),
            )
            for i in range(total)
        ]

        def select(_profile, *, observed_at, limit, include_personal_funding):
            self.assertTrue(include_personal_funding)
            self.assertLessEqual(limit, offset + ONGOING_LIMIT + 1)
            return tuple(entries[:limit])

        def serialize(entry):
            return {
                "kind": "project",
                "source": {"kind": "project", "id": f"test-project-{entry.number}"},
                "title": f"Projet {entry.number}",
                "summary": "Une suite existe.",
                "state": "active",
                "ready": [],
                "actor_interventions": [],
                "continuation": None,
                "blocker": None,
                "next": None,
                "timing": {},
                "place": None,
                "capabilities": [],
                "links": {},
            }

        with (
            patch("core.api.personal_projections.build_personal_ongoing_read_model",
                  side_effect=select),
            patch("core.api.personal_projections.pass_ongoing_candidates_through_molongo",
                  side_effect=lambda rows: rows),
            patch("core.api.personal_projections._project_ongoing_item",
                  side_effect=serialize),
            patch("core.api.personal_projections._attach_ongoing_recognition_media"),
        ):
            return build_personal_ongoing_projection(
                self.profile,
                observed_at=timezone.now(),
                continuation_offset=offset,
            )

    def test_server_pages_are_bounded_and_exhausted_truthfully(self):
        first = self._projection()
        self.assertEqual(len(first["items"]), ONGOING_LIMIT)
        self.assertEqual(first["continuation"]["state"], "more")
        self.assertEqual(first["coverage_state"], "partial")
        second_offset = ongoing_continuation_offset(
            first["continuation"]["token"], profile=self.profile,
        )
        self.assertEqual(second_offset, ONGOING_LIMIT)
        second = self._projection(offset=second_offset)
        self.assertEqual(len(second["items"]), ONGOING_LIMIT)
        third_offset = ongoing_continuation_offset(
            second["continuation"]["token"], profile=self.profile,
        )
        last = self._projection(offset=third_offset)
        self.assertEqual(len(last["items"]), 3)
        self.assertEqual(last["continuation"], {"state": "end", "token": None})
        self.assertEqual(last["coverage_state"], "complete")
        identities = [row["id"] for page in (first, second, last) for row in page["items"]]
        self.assertEqual(len(identities), len(set(identities)))

    def test_signed_cursor_cannot_cross_profile(self):
        first = self._projection()
        with self.assertRaises(ValueError):
            ongoing_continuation_offset(
                first["continuation"]["token"], profile=self.other,
            )

    def test_signed_offset_must_be_positive_aligned_integer(self):
        for offset in (-1, 0, 1, ONGOING_LIMIT + 1, "18", True):
            token = signing.dumps(
                {"offset": offset, "viewer": str(self.profile.pk)},
                salt=ONGOING_CONTINUATION_SALT,
            )
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                ongoing_continuation_offset(token, profile=self.profile)

    def test_corrupt_cursor_is_not_retreated_as_first_page(self):
        with self.assertRaises(signing.BadSignature):
            ongoing_continuation_offset("invalid", profile=self.profile)

    def test_empty_owner_has_no_n1_units(self):
        empty = self._projection(total=0)
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["continuation"]["state"], "end")
        self.assertEqual(empty["selection"]["state"], "empty")

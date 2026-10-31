"""Now N1 pagination: owner admission precedes slicing; cursors are private."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import SimpleTestCase
from django.utils import timezone

from core.api.personal_projections import (
    NOW_LIMIT,
    build_personal_now_projection,
    _decorate_now_semantics,
    now_continuation_offset,
)


class NowContinuationTests(SimpleTestCase):
    def setUp(self):
        self.profile = SimpleNamespace(pk=uuid4())
        self.other = SimpleNamespace(pk=uuid4())

    def _projection(self, *, count=NOW_LIMIT * 2 + 3, offset=0):
        examples = [
            {
                "id": f"personal-now-{i}",
                "key": f"personal-now-{i}",
                "source": {"kind": "dossier", "id": str(uuid4())},
                "dimension": "adaptation",
                "kind": "dossier.dependency",
                "business_actions": [],
                "human_context": f"Situation {i}",
            }
            for i in range(count)
        ]
        with (
            patch(
                "core.api.personal_projections.resolve_mature_home_contextual_actions",
                return_value=(SimpleNamespace(actions=[]), {}),
            ),
            patch(
                "core.api.personal_projections.dossier_dependency_now_situations",
                return_value=examples,
            ),
        ):
            return build_personal_now_projection(
                self.profile,
                observed_at=timezone.now(),
                continuation_offset=offset,
            )

    def test_pages_are_bounded_and_terminal_only_after_last_item(self):
        first = self._projection()
        self.assertEqual(len(first["items"]), NOW_LIMIT)
        self.assertEqual(first["continuation"]["state"], "more")
        self.assertEqual(first["coverage_state"], "partial")
        self.assertEqual(first["items"][0]["id"], "personal-now-0")

        second_offset = now_continuation_offset(
            first["continuation"]["token"], profile=self.profile
        )
        self.assertEqual(second_offset, NOW_LIMIT)
        second = self._projection(offset=second_offset)
        self.assertEqual(len(second["items"]), NOW_LIMIT)
        self.assertEqual(second["continuation"]["state"], "more")
        third_offset = now_continuation_offset(
            second["continuation"]["token"], profile=self.profile
        )
        last = self._projection(offset=third_offset)
        self.assertEqual(len(last["items"]), 3)
        self.assertEqual(last["continuation"], {"state": "end", "token": None})
        self.assertEqual(last["coverage_state"], "complete")

    def test_cursor_cannot_be_used_by_another_profile(self):
        first = self._projection()
        with self.assertRaises(ValueError):
            now_continuation_offset(
                first["continuation"]["token"], profile=self.other
            )

    def test_bad_cursor_does_not_become_page_one(self):
        with self.assertRaises(signing.BadSignature):
            now_continuation_offset("invalid", profile=self.profile)

    def test_empty_owner_projection_is_the_only_calm_case(self):
        empty = self._projection(count=0)
        self.assertEqual(empty["selection"]["state"], "empty")
        self.assertEqual(empty["actor_attention_state"], "calm")
        self.assertIsNone(empty["continuation"])
        self.assertEqual(empty["terminal"]["state"], "empty")

    def test_s1_owner_freshness_is_not_inferred_from_projection_time(self):
        action = SimpleNamespace(
            reason_codes=(),
            actionability=SimpleNamespace(value="needs_attention"),
            summary="Une décision est attendue.",
            label="Consulter",
            kind="journey.needs_attention",
        )
        item = {
            "source": {"kind": "journey", "id": str(uuid4())},
            "dimension": "adaptation",
            "links": {},
            "timing": {},
        }
        _decorate_now_semantics(action, item, observed_at=timezone.now())
        self.assertEqual(item["knowledge_context"]["freshness"]["state"], "unknown")
        self.assertEqual(item["consequence"]["state"], "unknown")
        self.assertIsNone(item["consequence"]["effect"])
        self.assertEqual(item["turn"]["type"], "none")

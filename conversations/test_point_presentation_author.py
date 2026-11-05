from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from conversations.api_views import _serialize_point


def _point(*, author, represented_space=None):
    return SimpleNamespace(
        pk="point-1",
        conversation_id="conversation-1",
        conversation=SimpleNamespace(lifecycle="closed"),
        kind="information",
        response_mode="none",
        lifecycle="open",
        response_status={},
        allow_response_change=False,
        supersedes_id=None,
        importance="normal",
        title="Préparation",
        body="Contenu autorisé",
        requires_acknowledgement=False,
        opens_at=None,
        deadline_at=None,
        valid_until=None,
        options=SimpleNamespace(all=lambda: []),
        published_by=author,
        published_by_id=author.pk,
        represented_space=represented_space,
        represented_space_id=(represented_space.pk if represented_space else None),
        published_at=None,
        updated_at=None,
    )


class ConversationPointAuthorProjectionTests(SimpleTestCase):
    def _serialize(self, point, viewer):
        with (
            patch("conversations.api_views.point_personal_result", return_value={}),
            patch("conversations.api_views.visible_attachments_for_profile", return_value=[]),
        ):
            return _serialize_point(point, profile=viewer, section="history")

    def test_point_has_minimal_author_identity_and_viewer_ownership(self):
        person = SimpleNamespace(
            pk="user-1", username="marie", phone="private",
            email="private@example.test", get_full_name=lambda: "Marie N.",
        )
        own = self._serialize(_point(author=person), person)
        self.assertEqual(
            own["author"],
            {"label": "Marie N.", "is_mine": True, "represented_space": False},
        )
        self.assertNotIn("published_by_id", own)
        self.assertNotIn("email", str(own))
        self.assertNotIn("phone", str(own))

    def test_point_represented_space_is_not_a_global_profile(self):
        person = SimpleNamespace(
            pk="user-1", username="marie", get_full_name=lambda: "Marie N.",
        )
        viewer = SimpleNamespace(pk="user-2")
        space = SimpleNamespace(pk="space-1", name="Coopérative")
        other = self._serialize(
            _point(author=person, represented_space=space), viewer,
        )
        self.assertEqual(
            other["author"],
            {"label": "Coopérative", "is_mine": False, "represented_space": True},
        )
        self.assertNotIn("user-1", str(other))
        self.assertNotIn("space-1", str(other))

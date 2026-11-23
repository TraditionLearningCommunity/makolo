"""Targeted privacy contract for Conversation detail presentation."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from conversations.detail_presentation import (
    _safe_local_image,
    conversation_members_for_profile,
    conversation_media_for_profile,
    conversation_subject_for_profile,
)


class ConversationDetailPresentationTests(SimpleTestCase):
    def test_image_rejects_remote_and_malformed_urls(self):
        self.assertEqual(_safe_local_image("/media/portraits/one.jpg"),
                         "/media/portraits/one.jpg")
        for url in (
            "https://external.example/pic.png", "//external.example/pic.png",
            "javascript:alert(1)", "/media/a.png?secret=123",
            "/media/a.png#fragment", "avatar.png",
        ):
            with self.subTest(url=url):
                self.assertIsNone(_safe_local_image(url))

    def test_derived_group_audience_never_lists_people(self):
        viewer = SimpleNamespace(pk="viewer")
        conversation = SimpleNamespace(
            context=SimpleNamespace(kind="group"),
        )
        with patch("conversations.detail_presentation.can_manage_conversation",
                   return_value=False):
            data = conversation_members_for_profile(viewer, conversation)
        self.assertEqual(data["scope"], "restricted")
        self.assertEqual(data["people"], [])
        self.assertIs(data["can_manage"], False)
        self.assertNotIn("total_count", data)
        self.assertNotIn("invitations", data)
        self.assertNotIn("collectives", data)

    def test_direct_avatar_obeys_profile_visibility(self):
        viewer = SimpleNamespace(pk="viewer")
        other = SimpleNamespace(
            pk="other", full_name="Léa", username="lea", is_active=True,
            avatar=SimpleNamespace(url="/media/private.jpg"),
        )
        context = SimpleNamespace(
            kind="direct", direct_profile_a_id="viewer",
            direct_profile_a=viewer, direct_profile_b=other,
        )
        conversation = SimpleNamespace(context=context)
        with (
            patch("conversations.detail_presentation._public_context_image",
                  return_value=None),
            patch("accounts.profile_visibility.ProfileVisibilityResolver") as resolver,
            patch("sharing.passport.profile_has_public_passport", return_value=True),
        ):
            resolver.return_value.field.return_value = False
            data = conversation_subject_for_profile(viewer, conversation, "Léa")
            self.assertEqual(data["label"], "Léa")
            self.assertIsNone(data["image_url"])
            resolver.return_value.field.assert_called_with("avatar")
            resolver.return_value.field.return_value = True
            data = conversation_subject_for_profile(viewer, conversation, "Léa")
            self.assertEqual(data["image_url"], "/media/private.jpg")
            self.assertEqual(data["route"], "/people/other")

    def test_only_authorized_attachments_appear_in_media_index(self):
        viewer = SimpleNamespace(pk="viewer")
        conversation = SimpleNamespace(pk="conv")
        point = SimpleNamespace(pk="p1")
        attachment = SimpleNamespace(
            pk="attachment", point=point, kind="file", original_name="secret.pdf",
            mime_type="application/pdf", size=250,
        )
        with (
            patch("conversations.detail_presentation.ConversationPoint.objects") as points,
            patch("conversations.detail_presentation.ConversationPointAttachment.objects") as media,
            patch("conversations.detail_presentation.point_visible_to",
                  return_value=True),
            patch("conversations.detail_presentation.can_download_attachment",
                  return_value=False),
        ):
            points.filter.return_value.exclude.return_value = Mock()
            media.filter.return_value.select_related.return_value.order_by.return_value.__getitem__ = Mock(
                return_value=[attachment],
            )
            self.assertEqual(
                conversation_media_for_profile(viewer, conversation), [],
            )

    def test_group_count_is_only_returned_to_a_manager(self):
        viewer = SimpleNamespace(pk="owner")
        group = SimpleNamespace(pk="group-1", slug="group-1", name="Groupe 1")
        conversation = SimpleNamespace(context=SimpleNamespace(
            kind="group", group=group,
        ))
        person = SimpleNamespace(pk="member", full_name="Marie", username="marie")
        row = SimpleNamespace(profile=person, profile_id="member")
        with (
            patch("conversations.detail_presentation.can_manage_conversation",
                  return_value=True),
            patch("conversations.detail_presentation.ConversationParticipation.objects") as participants,
            patch("conversations.core_models.ConversationInvitation.objects") as invitations,
            patch("conversations.participant_services.conversation_collectives_for_manager",
                  return_value=[]),
            patch("groups.services.has_group_permission", return_value=True),
            patch("groups.models.GroupMembership.objects") as memberships,
        ):
            participants.filter.return_value.select_related.return_value.order_by.return_value.__getitem__ = Mock(
                return_value=[],
            )
            invitations.filter.return_value.select_related.return_value.order_by.return_value.__getitem__ = Mock(
                return_value=[],
            )
            memberships.filter.return_value.count.return_value = 247
            memberships.filter.return_value.select_related.return_value.order_by.return_value.__getitem__ = Mock(
                return_value=[row],
            )
            data = conversation_members_for_profile(viewer, conversation)
        self.assertEqual(data["scope"], "group")
        self.assertTrue(data["can_manage"])
        self.assertEqual(data["people"], [])
        self.assertEqual(data["derived"]["count"], 247)
        self.assertEqual(data["derived"]["people"], [
            {"identifier": "marie", "label": "Marie", "is_me": False},
        ])

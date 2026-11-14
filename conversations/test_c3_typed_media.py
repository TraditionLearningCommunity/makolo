from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import ExitStack

from django.core.exceptions import ValidationError
from django.test import TestCase

from conversations.rich_services import upload_conversation_media


class TypedConversationMediaTests(TestCase):
    def _context(self):
        actor = SimpleNamespace(pk="author")
        conversation = SimpleNamespace(
            lifecycle="open",
            policy=SimpleNamespace(allow_images=True),
        )
        uploaded = SimpleNamespace(name="style.png")
        point = Mock()
        point.attachments.filter.return_value.order_by.return_value.first.return_value = None
        attachment = SimpleNamespace(kind="image", content_hash="digest")
        patches = [
            patch("conversations.rich_services.can_view_conversation", return_value=True),
            patch("conversations.rich_services._validate_represented_context"),
            patch("conversations.rich_services.validate_conversation_upload",
                  return_value=(b"png-data", "image/png", "digest")),
            patch("conversations.rich_services.create_point_attachment",
                  return_value=attachment),
        ]
        return actor, conversation, uploaded, point, attachment, patches

    def test_question_with_photo_remains_one_structured_point(self):
        actor, conversation, uploaded, point, attachment, patches = self._context()
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            publish = stack.enter_context(patch(
                "conversations.rich_services.publish_composed_point",
                return_value=point,
            ))
            result, media = upload_conversation_media(
                actor=actor, conversation=conversation, uploaded_file=uploaded,
                kind="image", client_reference="one-intent",
                point_kind="question", title="Vous aimez ce style ?",
                body="Regardez la photo",
            )
        self.assertIs(result, point)
        self.assertIs(media, attachment)
        self.assertEqual(publish.call_args.kwargs["kind"], "question")
        self.assertEqual(publish.call_args.kwargs["client_reference"], "one-intent")

    def test_form_with_attachment_uses_questionnaire_owner(self):
        actor, conversation, uploaded, point, _, patches = self._context()
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            publish = stack.enter_context(patch(
                "conversations.rich_services.publish_conversation_form",
                return_value=point,
            ))
            result, _ = upload_conversation_media(
                actor=actor, conversation=conversation, uploaded_file=uploaded,
                kind="image", client_reference="form-intent",
                point_kind="form_request", title="Documents à préparer",
                questions=["Quel est votre nom ?"], audience_id="audience",
            )
        self.assertIs(result, point)
        self.assertEqual(publish.call_args.kwargs["questions"], ["Quel est votre nom ?"])
        self.assertEqual(publish.call_args.kwargs["client_reference"], "form-intent")

    def test_unknown_or_mixed_structured_targets_fail_closed(self):
        actor, conversation, uploaded, _, _, patches = self._context()
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            with self.assertRaises(ValidationError):
                upload_conversation_media(
                    actor=actor, conversation=conversation, uploaded_file=uploaded,
                    kind="image", client_reference="bad-intent",
                    point_kind="unknown", title="Unknown",
                )
            with self.assertRaises(ValidationError):
                upload_conversation_media(
                    actor=actor, conversation=conversation, uploaded_file=uploaded,
                    kind="image", client_reference="mixed-intent",
                    point_kind="question", point_id="other-point",
                    title="Question",
                )

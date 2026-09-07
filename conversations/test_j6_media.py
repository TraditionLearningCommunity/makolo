from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .media_models import ConversationAttachmentKind
from .media_services import attachment_for_download, create_point_attachment
from .point_models import ConversationPointKind
from .point_services import create_point
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationMediaTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j6-media-owner", email="j6-media-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j6-media-member", email="j6-media-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j6-media-outsider", email="j6-media-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J6 Media Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J6 Media Activity")
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="j6-conversations-media",
        )
        self.conversation = ensure_context_conversation(actor=self.owner, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        # Visibility audiences narrow legitimate access; explicit participation is
        # the live access boundary for this media recipient fixture.
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.member)
        audience = create_audience_set(actor=self.owner, conversation=self.conversation, label="Destinataire média")
        add_audience_rule(
            actor=self.owner,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )
        self.point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Document de coordination",
            visibility_audience=audience,
        )

    def _upload(self):
        return SimpleUploadedFile("consignes.txt", b"consignes privees", content_type="text/plain")

    def test_point_attachment_uses_private_storage_without_public_url(self):
        attachment = create_point_attachment(
            actor=self.owner,
            point=self.point,
            uploaded_file=self._upload(),
            kind=ConversationAttachmentKind.FILE,
        )
        self.assertEqual(attachment.original_name, "consignes.txt")
        self.assertEqual(attachment.mime_type, "text/plain")
        with self.assertRaises(ValueError):
            _ = attachment.file.url

    def test_visible_profile_can_download_and_outsider_cannot(self):
        attachment = create_point_attachment(
            actor=self.owner,
            point=self.point,
            uploaded_file=self._upload(),
            kind=ConversationAttachmentKind.FILE,
        )
        self.assertEqual(attachment_for_download(actor=self.member, attachment_id=attachment.pk).pk, attachment.pk)
        with self.assertRaises(PermissionDenied):
            attachment_for_download(actor=self.outsider, attachment_id=attachment.pk)

        self.client.force_login(self.member)
        allowed = self.client.get(reverse("conversations:attachment", kwargs={"attachment_pk": attachment.pk}))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed["Cache-Control"], "private, no-store")

        self.client.force_login(self.outsider)
        denied = self.client.get(reverse("conversations:attachment", kwargs={"attachment_pk": attachment.pk}))
        self.assertEqual(denied.status_code, 404)

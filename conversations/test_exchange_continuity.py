import json
from unittest.mock import AsyncMock, patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from .test_exchange_stream import ExchangeFixture
from .entry_projection import project_entry
from .entry_services import acknowledge_entries, delete_entry
from .exchange_list_projection import exchange_list_summary
from .services import update_personal_conversation_state


class ExchangeContinuityTests(ExchangeFixture, TestCase):
    def test_message_refreshes_parent_list_order_without_a_new_attention_state(self):
        from datetime import timedelta
        from django.utils import timezone
        type(self.conversation).objects.filter(pk=self.conversation.pk).update(updated_at=timezone.now()-timedelta(days=100))
        entry=self.send()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.updated_at,entry.created_at)

    def artifact(self,kind="cv"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from journeys.services import create_journey
        from journeys.models import WorkflowKind
        from journeys.collaboration_services import create_artifact
        journey=create_journey(initiated_by=self.owner,beneficiary=self.owner,activity=self.activity,workflow=WorkflowKind.REGISTRATION)
        artifact=create_artifact(journey=journey,uploaded_by=self.owner,uploaded_file=SimpleUploadedFile("document.txt",b"Document prive",content_type="text/plain"),kind=kind,title="Document")
        self.addCleanup(artifact.file.delete,save=False)
        entry=self.send(references=[{"kind":"journey_artifact","id":str(artifact.pk)}])
        return artifact,entry.references.get()

    def test_reference_view_and_export_recheck_both_entry_and_artifact_owners(self):
        artifact,reference=self.artifact()
        self.client.force_login(self.owner)
        url=reverse("conversations-api:entry-reference-file",kwargs={"reference_pk":reference.pk})
        response=self.client.get(url);self.assertEqual(response.status_code,200);response.close()
        self.assertEqual(self.client.get(url,{"mode":"download"}).status_code,409)
        response=self.client.get(url,{"mode":"download","confirm":"1"});self.assertEqual(response.status_code,200);response.close()
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.get(url,{"mode":"download","confirm":"1"}).status_code,403)

    def test_view_access_does_not_turn_blocked_document_kind_into_export_authority(self):
        artifact,reference=self.artifact(kind="identity_document")
        self.client.force_login(self.owner)
        url=reverse("conversations-api:entry-reference-file",kwargs={"reference_pk":reference.pk})
        response=self.client.get(url);self.assertEqual(response.status_code,200);response.close()
        self.assertEqual(self.client.get(url,{"mode":"download","confirm":"1"}).status_code,403)

    def test_unopened_conversation_summary_uses_entry_acl_and_separate_unread(self):
        self.send(body="Visible")
        self.assertEqual(exchange_list_summary(self.member,self.conversation)["unread_count"],1)
        self.point.response_visibility="respondent_and_authorities";self.point.save()
        summary=exchange_list_summary(self.member,self.conversation)
        self.assertIsNone(summary["last_message"])
        self.assertEqual(summary["unread_count"],0)

    @override_settings(CONVERSATIONS_REALTIME_ENABLED=True)
    @patch("conversations.realtime_events.get_channel_layer")
    def test_commit_fanout_invalidates_unopened_inboxes_without_private_content(self,layer):
        layer.return_value.group_send=AsyncMock()
        with self.captureOnCommitCallbacks(execute=True):self.send(body="Corps strictement privé")
        frames=[call.args for call in layer.return_value.group_send.call_args_list]
        self.assertTrue(any(group==f"conversation.inbox.{self.member.pk}" for group,event in frames))
        for group,event in frames:self.assertNotIn("Corps strictement privé",json.dumps(event))

    def test_targeted_context_finds_a_quote_outside_the_first_history_page(self):
        target=self.send(reference="target")
        for i in range(55):self.send(body=f"Suite {i}",reference=f"suite-{i}")
        self.client.force_login(self.member)
        page=self.client.get(self.url("entry-detail",entry_pk=target.pk)).json()
        self.assertEqual(page["target_id"],str(target.pk))
        self.assertLessEqual(len(page["results"]),51)
        self.assertIn(str(target.pk),{row["id"] for row in page["results"]})

    def test_inaccessible_quote_does_not_acquire_surrounding_history(self):
        target=self.send();self.client.force_login(self.outsider)
        with patch("conversations.entry_api.projected_rows") as project:
            response=self.client.get(self.url("entry-detail",entry_pk=target.pk))
        self.assertEqual(response.status_code,404);project.assert_not_called()

    def test_removed_target_returns_tombstone_with_same_navigation_identity(self):
        target=self.send();delete_entry(actor=self.owner,entry=target);self.client.force_login(self.member)
        page=self.client.get(self.url("entry-detail",entry_pk=target.pk)).json()
        row=next(row for row in page["results"] if row["id"]==str(target.pk))
        self.assertTrue(row["removed"]);self.assertEqual(row["body"],"")

    def test_search_pages_are_disjoint_and_keep_server_visibility(self):
        for i in range(55):self.send(body=f"Recherche {i}",reference=f"search-{i}")
        self.client.force_login(self.member)
        first=self.client.get(self.url("entry-search"),{"q":"Recherche"}).json()
        second=self.client.get(self.url("entry-search"),{"q":"Recherche","cursor":first["next_cursor"]}).json()
        self.assertEqual(len(first["results"]),50);self.assertEqual(len(second["results"]),5)
        self.assertFalse({r["id"] for r in first["results"]}&{r["id"] for r in second["results"]})

    def test_read_privacy_hides_disclosure_without_losing_own_unread_watermark(self):
        entry=self.send();acknowledge_entries(actor=self.member,point=self.point,delivered_sequence=entry.sequence,read_sequence=entry.sequence)
        update_personal_conversation_state(actor=self.member,conversation=self.conversation,share_read_receipts=False)
        self.assertEqual(project_entry(self.owner,entry)["delivery"]["read_count"],0)
        self.assertEqual(exchange_list_summary(self.member,self.conversation)["unread_count"],0)

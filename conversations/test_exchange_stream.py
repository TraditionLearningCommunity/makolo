"""Owner/ACL/continuity contracts. Written for manual execution, not run here."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from redis.exceptions import ConnectionError as RedisConnectionError

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization
from .core_models import ConversationContextKind
from .entry_models import ConversationEntryReceipt
from .entry_projection import project_entry
from .entry_services import (ExchangeConflict, acknowledge_entries, delete_entry, edit_entry,
                             react_entry, send_entry)
from .media_services import can_download_attachment
from .point_services import create_point
from .services import activate_participation, ensure_context_conversation, remove_participation

User = get_user_model()


class ExchangeFixture:
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="exchange-owner")
        self.member = User.objects.create_user(username="exchange-member")
        self.outsider = User.objects.create_user(username="exchange-outsider")
        self.space = Organization.objects.create(name="Exchange scope", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="Coordination")
        grant_activity_role(profile=self.owner, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
                            granted_by=self.owner, source="exchange-test")
        self.conversation = ensure_context_conversation(actor=self.owner, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        self.participation = activate_participation(actor=self.owner, conversation=self.conversation, profile=self.member)
        self.point = create_point(actor=self.owner, conversation=self.conversation, kind="exchange", title="Discussion",
                                  response_visibility="point_viewers")

    def send(self, *, body="Message initial", reference="entry-initial", actor=None, **kwargs):
        return send_entry(actor=actor or self.owner, point=self.point, body=body, client_reference=reference, **kwargs)

    def url(self, name, **kwargs):
        return reverse("conversations-api:" + name, kwargs=kwargs or {"point_pk": self.point.pk})

    def edit(self, entry, *, body="Texte modifié", version=1, reference="edit-initial"):
        return edit_entry(actor=self.owner, entry=entry, body=body, expected_edit_version=version, client_reference=reference)


class ExchangeStreamTests(ExchangeFixture, TestCase):
    def test_sequences_and_versions_belong_to_point(self):
        first = self.send()
        second = self.send(body="Suite", reference="entry-next")
        other = create_point(actor=self.owner, conversation=self.conversation, kind="exchange")
        third = send_entry(actor=self.owner, point=other, body="Autre", client_reference="entry-other")
        self.assertEqual((first.sequence, second.sequence, third.sequence), (1, 2, 1))
        self.assertGreater(second.last_change_version, first.last_change_version)

    def test_ack_lost_replay_survives_later_edit(self):
        entry = self.send()
        self.edit(entry)
        replay = self.send()
        self.assertEqual(replay.pk, entry.pk)
        self.assertEqual(replay.body, "Texte modifié")
        self.assertEqual(self.point.exchange_entries.count(), 1)

    def test_changed_origin_payload_conflicts(self):
        self.send()
        with self.assertRaises(ExchangeConflict):
            self.send(body="Intention différente")

    def test_conflict_is_http_409_on_existing_endpoint(self):
        self.send()
        self.client.force_login(self.owner)
        response = self.client.post(self.url("exchange-entries"), data=json.dumps({"body": "Autre", "client_reference": "entry-initial"}), content_type="application/json")
        self.assertEqual(response.status_code, 409)

    def test_edited_message_keeps_identity_and_sequence(self):
        entry = self.send()
        edited = self.edit(entry)
        self.assertEqual((edited.pk, edited.sequence, edited.edit_version), (entry.pk, 1, 2))
        revision = edited.revisions.get()
        self.assertNotIn("Message initial", revision.old_content_sha256)
        self.assertEqual(len(revision.old_content_sha256), 64)

    def test_concurrent_editor_version_conflicts_and_retry_is_idempotent(self):
        entry = self.send()
        edited = self.edit(entry)
        self.assertEqual(self.edit(entry).pk, edited.pk)
        with self.assertRaises(ExchangeConflict):
            self.edit(entry, body="Autre", reference="edit-other")
        self.assertEqual(edited.revisions.count(), 1)

    def test_non_author_cannot_edit(self):
        entry = self.send()
        with self.assertRaises(PermissionDenied):
            edit_entry(actor=self.member, entry=entry, body="Autre", expected_edit_version=1, client_reference="edit-member")

    def test_private_reply_cannot_be_quoted(self):
        self.point.response_visibility = "respondent_and_authorities"
        self.point.save()
        private = self.send()
        with self.assertRaises(PermissionDenied):
            self.send(actor=self.member, body="Citation", reference="quote-private", reply_to=private)

    def test_reply_must_belong_to_same_point(self):
        other = create_point(actor=self.owner, conversation=self.conversation, kind="exchange")
        entry = send_entry(actor=self.owner, point=other, body="Autre", client_reference="foreign-message")
        with self.assertRaises(PermissionDenied):
            self.send(reply_to=entry)

    def test_deleted_quote_is_a_tombstone_and_joins_delta(self):
        original = self.send()
        quote = self.send(body="Citation", reference="quote", reply_to=original)
        before = quote.last_change_version
        delete_entry(actor=self.owner, entry=original)
        quote.refresh_from_db()
        self.assertGreater(quote.last_change_version, before)
        result = project_entry(self.member, quote)
        self.assertTrue(result["reply_to"]["removed"])
        self.assertEqual(result["reply_to"]["body"], "")

    def test_reaction_add_remove_is_idempotent_and_versioned(self):
        entry = self.send()
        react_entry(actor=self.member, entry=entry, emoji="👍", selected=True)
        version = self.point.exchange_entries.get(pk=entry.pk).last_change_version
        react_entry(actor=self.member, entry=entry, emoji="👍", selected=True)
        entry.refresh_from_db()
        self.assertEqual(entry.last_change_version, version)
        self.assertEqual(entry.reactions.count(), 1)
        react_entry(actor=self.member, entry=entry, emoji="👍", selected=False)
        self.assertFalse(entry.reactions.exists())

    def test_unknown_emoji_and_outsider_mentions_are_rejected(self):
        entry = self.send()
        with self.assertRaises(ValidationError):
            react_entry(actor=self.member, entry=entry, emoji="unbounded", selected=True)
        with self.assertRaises(ValidationError):
            self.send(reference="mention-private", mention_profile_ids=[self.outsider.pk])

    def test_receipts_are_monotone_and_bound_to_visible_sequences(self):
        first = self.send()
        second = self.send(reference="second")
        acknowledge_entries(actor=self.member, point=self.point, delivered_sequence=second.sequence, read_sequence=second.sequence)
        acknowledge_entries(actor=self.member, point=self.point, delivered_sequence=first.sequence, read_sequence=0)
        receipt = ConversationEntryReceipt.objects.get(point=self.point, profile=self.member)
        self.assertEqual((receipt.delivered_sequence, receipt.read_sequence), (2, 2))
        with self.assertRaises(ValidationError):
            acknowledge_entries(actor=self.member, point=self.point, delivered_sequence=99, read_sequence=0)

    def test_receipts_cannot_ack_private_message(self):
        self.point.response_visibility = "respondent_and_authorities"
        self.point.save()
        entry = self.send()
        with self.assertRaises(ValidationError):
            acknowledge_entries(actor=self.member, point=self.point, delivered_sequence=entry.sequence, read_sequence=0)

    def test_delta_pages_do_not_skip_later_edit_of_old_entry(self):
        first = self.send()
        self.send(reference="second")
        self.client.force_login(self.member)
        url = self.url("entry-sync")
        page1 = self.client.get(url, {"after_version": 0, "limit": 1}).json()
        self.edit(first)
        page2 = self.client.get(url, {"after_version": page1["next_version"], "limit": 1}).json()
        page3 = self.client.get(url, {"after_version": page2["next_version"], "limit": 1}).json()
        self.assertEqual(page3["results"][0]["id"], str(first.pk))
        self.assertEqual(page3["results"][0]["body"], "Texte modifié")

    def test_backward_pagination_and_private_search(self):
        for index in range(4):
            self.send(reference=f"history-{index}", body=f"Rendez-vous {index}")
        self.client.force_login(self.member)
        page = self.client.get(self.url("exchange-entries"), {"order": "latest", "limit": 2}).json()
        self.assertEqual([row["sequence"] for row in page["results"]], [3, 4])
        older = self.client.get(self.url("exchange-entries"), {"before_sequence": page["before_sequence"], "limit": 2}).json()
        self.assertEqual([row["sequence"] for row in older["results"]], [1, 2])
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url("entry-search"), {"q": "Rendez-vous"}).status_code, 404)

    def test_revocation_blocks_sync_and_hides_client_reference_from_other_viewer(self):
        entry = self.send()
        self.assertNotIn("client_reference", project_entry(self.member, entry))
        remove_participation(actor=self.owner, participation=self.participation)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url("entry-sync")).status_code, 404)

    def test_media_only_is_atomic_and_revoked_by_tombstone(self):
        data = SimpleUploadedFile("note.txt", b"Document prive", content_type="text/plain")
        entry = self.send(body="", uploaded_media={"file": data, "kind": "file"})
        self.assertEqual(entry.body, "")
        attachment = entry.attachments.get()
        self.assertTrue(can_download_attachment(self.member, attachment))
        removed = delete_entry(actor=self.owner, entry=entry)
        attachment.exchange_entry = removed
        self.assertFalse(can_download_attachment(self.owner, attachment))
        self.assertEqual(project_entry(self.member, removed)["attachments"], [])

    def test_malformed_upload_never_creates_empty_message(self):
        data = SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            self.send(body="", uploaded_media={"file": data, "kind": "file"})
        self.assertEqual(self.point.exchange_entries.count(), 0)

    def test_migration_legacy_media_replay_still_matches_after_edit(self):
        file = SimpleUploadedFile("note.txt", b"Document prive", content_type="text/plain")
        entry = self.send(body="note.txt", uploaded_media={"file": file, "kind": "file"})
        type(entry).objects.filter(pk=entry.pk).update(origin_payload_hash="")
        self.edit(entry)
        file = SimpleUploadedFile("note.txt", b"Document prive", content_type="text/plain")
        replay = self.send(body="", uploaded_media={"file": file, "kind": "file"})
        self.assertEqual(replay.pk, entry.pk)

    def test_ack_replay_does_not_republish_a_revoked_mention(self):
        entry = self.send(mention_profile_ids=[self.member.pk])
        remove_participation(actor=self.owner, participation=self.participation)
        replay = self.send(mention_profile_ids=[self.member.pk])
        self.assertEqual(replay.pk, entry.pk)
        self.assertEqual(project_entry(self.owner, replay)["mentions"], [])

    def test_reference_visibility_rechecks_requirement_owner_without_granting_access(self):
        from requirements.domain_services import create_requirement_definition
        from .entry_models import ConversationEntryReference
        requirement = create_requirement_definition(actor=self.owner, activity=self.activity, key="document", title="Document requis")
        entry = self.send(references=[{"kind": "requirement_definition", "id": str(requirement.pk)}])
        self.assertTrue(project_entry(self.owner, entry)["references"][0]["available"])
        self.assertFalse(project_entry(self.member, entry)["references"][0]["available"])
        with self.assertRaises(PermissionDenied):
            self.send(actor=self.member, reference="member-reference", references=[{"kind":"requirement_definition", "id":str(requirement.pk)}])
        self.assertEqual(ConversationEntryReference.objects.filter(entry=entry).count(), 1)

    def test_profile_switch_header_prevents_acting_as_another_authenticated_person(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url("exchange-entries"), data=json.dumps({"body":"Autre", "client_reference":"profile-switch"}),
                                    content_type="application/json", HTTP_X_MAKOLO_PROFILE=str(self.owner.pk))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.point.exchange_entries.exists())

    @override_settings(CONVERSATIONS_REALTIME_ENABLED=True)
    @patch("conversations.realtime_events.get_channel_layer", side_effect=RedisConnectionError("unavailable"))
    def test_redis_outage_does_not_rollback_rest_commit(self, layer):
        with self.captureOnCommitCallbacks(execute=True):
            entry = self.send()
        self.assertTrue(self.point.exchange_entries.filter(pk=entry.pk).exists())


@skipUnless(connection.vendor == "postgresql", "Exchange lock evidence requires PostgreSQL")
class ExchangeConcurrencyTests(ExchangeFixture, TransactionTestCase):
    def race(self, same_reference):
        barrier = Barrier(2)
        def worker(index):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.owner.pk)
                from .point_models import ConversationPoint
                point = ConversationPoint.objects.get(pk=self.point.pk)
                barrier.wait(timeout=10)
                return send_entry(actor=actor, point=point, body="Concurrent", client_reference="race-shared" if same_reference else f"race-{index}").pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker, range(2)))

    def test_same_intent_concurrent_replay_is_one_message(self):
        self.assertEqual(len(set(self.race(True))), 1)
        self.assertEqual(self.point.exchange_entries.count(), 1)

    def test_distinct_concurrent_sends_get_distinct_sequences(self):
        self.race(False)
        self.assertEqual(list(self.point.exchange_entries.order_by("sequence").values_list("sequence", flat=True)), [1, 2])

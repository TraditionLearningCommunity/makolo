from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from notifications.models import Notification
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import Conversation, ConversationContextKind, ConversationInvitationStatus
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
from .services import (
    activate_participation,
    create_conversation_invitation,
    ensure_context_conversation,
    update_personal_conversation_state,
)


User = get_user_model()


class ConversationJ7ContractsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j7-contract-owner", email="j7-contract-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j7-contract-member", email="j7-contract-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j7-contract-outsider", email="j7-contract-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J7 Contract Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J7 Contract Activity")
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="j7-conversations-contracts",
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.member)
        self.audience = create_audience_set(actor=self.owner, conversation=self.conversation, label="J7 Member")
        add_audience_rule(
            actor=self.owner,
            audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )

    def _question(self, *, client_reference=None):
        return create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Texte privé à ne jamais copier dans un event",
            body="Contenu de coordination strictement privé",
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
            client_reference=client_reference,
        )

    def test_point_event_payload_is_minimal_and_content_free(self):
        point = self._question()
        event = DomainEventOutbox.objects.filter(
            event_type=DomainEventType.CONVERSATION_POINT_PUBLISHED,
            source_id=str(point.pk),
        ).get()
        self.assertEqual(event.payload["point_id"], str(point.pk))
        self.assertEqual(event.payload["conversation_id"], str(self.conversation.pk))
        serialized = str(event.payload)
        self.assertNotIn(point.title, serialized)
        self.assertNotIn(point.body, serialized)

    def test_action_notification_is_created_after_commit_and_mute_is_respected(self):
        with self.captureOnCommitCallbacks(execute=True):
            point = self._question(client_reference="j7-notify-1")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member,
                metadata__conversation_id=str(self.conversation.pk),
            ).exists()
        )

        Notification.objects.filter(recipient=self.member).delete()
        update_personal_conversation_state(actor=self.member, conversation=self.conversation, mute=True)
        with self.captureOnCommitCallbacks(execute=True):
            self._question(client_reference="j7-notify-muted")
        self.assertFalse(Notification.objects.filter(recipient=self.member).exists())

    def test_api_hides_conversation_from_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk}))
        self.assertEqual(response.status_code, 404)

    def test_c1_list_and_detail_keep_authorized_owner_projection_fields(self):
        point = self._question(client_reference="j7-c1-owner-projection")
        self.client.force_login(self.member)

        listing = self.client.get(reverse("conversations-api:list"))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing["Cache-Control"], "private, no-store")
        item = next(
            item for item in listing.json()["results"]
            if item["id"] == str(self.conversation.pk)
        )
        for field in (
            "title", "purpose", "context", "attention_count",
            "latest_result", "all_clear", "updated_at",
        ):
            self.assertIn(field, item)

        detail = self.client.get(
            reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail["Cache-Control"], "private, no-store")
        payload = detail.json()
        for field in ("purpose", "context", "points", "essential", "personal_state", "updated_at"):
            self.assertIn(field, payload)
        matching = [row for row in payload["points"] if row["id"] == str(point.pk)]
        self.assertEqual(len(matching), 1)
        for field in (
            "kind", "importance", "response_mode", "lifecycle", "title",
            "body", "options", "section", "attention_reason", "can_respond",
            "resolution_summary", "opens_at", "deadline_at", "valid_until",
            "published_at", "updated_at",
        ):
            self.assertIn(field, matching[0])

        self.client.force_login(self.outsider)
        self.assertNotIn(
            str(self.conversation.pk),
            [row["id"] for row in self.client.get(reverse("conversations-api:list")).json()["results"]],
        )
        self.assertEqual(
            self.client.get(
                reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
            ).status_code,
            404,
        )

    def test_c1_updated_after_requires_explicit_timezone(self):
        self.client.force_login(self.member)
        url = reverse("conversations-api:list")
        naive = self.client.get(url, {"updated_after": "2026-11-04T09:00:00"})
        self.assertEqual(naive.status_code, 400)
        self.assertIn("updated_after", naive.json())

        aware = self.client.get(url, {"updated_after": "2026-11-04T09:00:00Z"})
        self.assertEqual(aware.status_code, 200)
        self.assertIn("results", aware.json())

    def test_c2_context_entry_uses_existing_authorized_conversation(self):
        before = Conversation.objects.count()
        self.client.force_login(self.member)
        kwargs = {"kind": "activity", "context_pk": str(self.activity.pk)}
        web = self.client.get(reverse("conversations:by-context", kwargs=kwargs))
        self.assertRedirects(
            web, reverse("conversations:detail", kwargs={"pk": self.conversation.pk}),
        )
        api = self.client.get(reverse("conversations-api:by-context", kwargs=kwargs))
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api["Cache-Control"], "private, no-store")
        self.assertEqual(api.json()["count"], 1)
        self.assertEqual(api.json()["results"][0]["id"], str(self.conversation.pk))
        self.assertEqual(Conversation.objects.count(), before)

        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(reverse("conversations:by-context", kwargs=kwargs)).status_code,
            404,
        )
        response = self.client.get(reverse("conversations-api:by-context", kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["results"], [])
        self.assertFalse(response.json()["can_ensure"])
        self.assertEqual(Conversation.objects.count(), before)

    def test_c2_groups_visible_points_once_with_essential_and_elsewhere(self):
        information = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Entrée porte B", importance="important",
        )
        elsewhere = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Une question ouverte", response_audience=self.audience,
        )
        expected = self._question(client_reference="c2-member-expected")
        self.client.force_login(self.member)
        url = reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        payload = self.client.get(url).json()
        groups = (
            payload["points"], payload["essential"], payload["elsewhere"],
        )
        ids = [point["id"] for group in groups for point in group]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(str(information.pk), ids)
        self.assertIn(str(elsewhere.pk), ids)
        self.assertIn(str(expected.pk), ids)
        self.assertIn(str(elsewhere.pk), [point["id"] for point in payload["elsewhere"]])

        page = self.client.get(reverse("conversations:detail", kwargs={"pk": self.conversation.pk}))
        for pk in (information.pk, elsewhere.pk, expected.pk):
            self.assertContains(page, f'id="point-{pk}"', count=1)
        self.assertContains(page, "En cours ailleurs")
        self.assertContains(page, "À vous")

    def test_c2_search_focus_never_reveals_point_outside_audience(self):
        restricted = create_audience_set(
            actor=self.owner, conversation=self.conversation, label="Auteur seul",
        )
        add_audience_rule(
            actor=self.owner, audience_set=restricted,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.owner,
        )
        hidden = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Information réservée strictement", visibility_audience=restricted,
        )
        self.client.force_login(self.member)
        url = reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        detail = self.client.get(url, {"focus_point": str(hidden.pk)})
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertIsNone(payload["focused_point"])
        self.assertNotIn(
            str(hidden.pk),
            [point["id"] for field in ("points", "essential", "elsewhere") for point in payload[field]],
        )
        page = self.client.get(
            reverse("conversations:detail", kwargs={"pk": self.conversation.pk}),
            {"focus": str(hidden.pk)},
        )
        self.assertNotContains(page, "Information réservée strictement")
        results = self.client.get(
            reverse("conversations-api:list"), {"q": "réservée strictement"},
        )
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()["results"], [])

    def test_api_response_is_idempotent_by_client_reference(self):
        point = self._question(client_reference="j7-api-question")
        self.client.force_login(self.member)
        url = reverse("conversations-api:point-respond", kwargs={"point_pk": point.pk})
        first = self.client.post(
            url,
            {"value": "Réponse unique", "client_reference": "mobile-response-001"},
            content_type="application/json",
        )
        second = self.client.post(
            url,
            {"value": "Réponse unique", "client_reference": "mobile-response-001"},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(point.responses.filter(actor=self.member).count(), 1)

    def test_invitation_grants_no_detail_access_until_accepted(self):
        invitation = create_conversation_invitation(
            actor=self.owner,
            conversation=self.conversation,
            invitee=self.outsider,
            client_reference="j7-invite-outsider",
        )
        self.client.force_login(self.outsider)
        detail_url = reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        invitation_list = self.client.get(reverse("conversations-api:invitation-list"))
        self.assertEqual(invitation_list.status_code, 200)
        self.assertEqual(invitation_list.json()["count"], 1)

        response = self.client.post(
            reverse("conversations-api:invitation-respond", kwargs={"invitation_pk": invitation.pk}),
            {"decision": "accept"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ConversationInvitationStatus.ACCEPTED)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_detail_viewer_caches_preserve_point_selection(self):
        point = self._question(client_reference="j7-detail-cache-selection")
        from .presentation import now_points_for_profile, other_visible_points_for_profile

        baseline = now_points_for_profile(self.member, self.conversation, limit=20)
        cached = now_points_for_profile(
            self.member, self.conversation, limit=20,
            visibility_cache={}, audience_cache={}, history_cache={},
            attention_caches=({}, {}, {}),
        )
        self.assertEqual(
            [(row["point"].pk, row["reason"], row["section"]) for row in cached],
            [(row["point"].pk, row["reason"], row["section"]) for row in baseline],
        )
        self.assertIn(point.pk, [row["point"].pk for row in cached])

        baseline_other = other_visible_points_for_profile(
            self.member, self.conversation, limit=20,
        )
        cached_other = other_visible_points_for_profile(
            self.member, self.conversation, limit=20,
            visibility_cache={}, audience_cache={}, history_cache={},
        )
        self.assertEqual(
            [row.pk for row in cached_other], [row.pk for row in baseline_other],
        )
        self.assertEqual(
            now_points_for_profile(self.outsider, self.conversation),
            [],
        )

    def test_future_question_counts_as_upcoming_without_early_response(self):
        from .attention import point_attention_reason

        future_point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Question programmée",
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
            opens_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(point_attention_reason(self.member, future_point), "upcoming")
        self.client.force_login(self.member)
        presence = self.client.get(reverse("conversations-api:attention-presence"))
        self.assertEqual(presence.status_code, 200)
        self.assertEqual(presence.json(), {"has_attention": True})
        listing = self.client.get(reverse("conversations-api:list"))
        self.assertEqual(listing.status_code, 200)
        row = next(
            item for item in listing.json()["results"]
            if item["id"] == str(self.conversation.pk)
        )
        self.assertEqual(row["attention_count"], 1)
        detail = self.client.get(
            reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        )
        self.assertEqual(detail.status_code, 200)
        upcoming = next(
            item for item in detail.json()["points"]
            if item["id"] == str(future_point.pk)
        )
        self.assertEqual(upcoming["attention_reason"], "upcoming")
        self.assertEqual(upcoming["section"], "a_savoir")
        self.assertFalse(upcoming["can_respond"])

    def test_attention_presence_tracks_real_point_attention_not_unread_activity(self):
        point = self._question(client_reference="j7-presence-question")
        self.client.force_login(self.member)
        presence_url = reverse("conversations-api:attention-presence")

        present = self.client.get(presence_url)
        self.assertEqual(present.status_code, 200)
        self.assertEqual(present.json(), {"has_attention": True})
        self.assertEqual(present["Cache-Control"], "private, no-store")

        response = self.client.post(
            reverse("conversations-api:point-respond", kwargs={"point_pk": point.pk}),
            {"value": "Réponse confirmée", "client_reference": "j7-presence-response"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(presence_url).json(), {"has_attention": False})

    def test_personal_state_api_does_not_change_shared_lifecycle_and_mute_is_reversible(self):
        self.client.force_login(self.member)
        url = reverse(
            "conversations-api:personal-state",
            kwargs={"pk": self.conversation.pk},
        )
        before = self.conversation.lifecycle
        response = self.client.post(
            url,
            {"pinned": True, "archived": True, "revisit": True, "mute": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {key: response.json()[key] for key in ("pinned", "archived", "revisit", "muted")},
            {"pinned": True, "archived": True, "revisit": True, "muted": True},
        )
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lifecycle, before)

        unmuted = self.client.post(
            url,
            {"mute": False},
            content_type="application/json",
        )
        self.assertEqual(unmuted.status_code, 200)
        self.assertFalse(unmuted.json()["muted"])
        self.assertTrue(unmuted.json()["pinned"])

    def test_represented_point_retains_human_author_and_distinct_space_context(self):
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
            source="j7-represented-author",
        )
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Coordination humaine",
            represented_space=self.space,
            visibility_audience=self.audience,
        )
        self.client.force_login(self.member)
        detail = self.client.get(
            reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        )
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        points = (
            payload["points"] + payload["essential"] + payload["timeline"]
        )
        row = next(item for item in points if item["id"] == str(point.pk))
        self.assertEqual(row["author"]["label"], self.owner.username)
        self.assertEqual(row["author"]["space_label"], self.space.name)
        self.assertTrue(row["author"]["represented_space"])
        self.assertNotEqual(row["author"]["label"], self.space.name)

    def test_space_context_lookup_only_returns_visible_space_conversations(self):
        grant_space_role(
            profile=self.member,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
            source="j7-conversations-space-list",
        )
        space_conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.SPACE,
            space=self.space,
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(
                "conversations-api:by-context",
                kwargs={"kind": "space", "context_pk": self.space.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(space_conversation.pk), ids)
        # Activity discussions are not relabeled as the Space's conversation.
        self.assertNotIn(str(self.conversation.pk), ids)
        self.client.force_login(self.outsider)
        outsider = self.client.get(
            reverse(
                "conversations-api:by-context",
                kwargs={"kind": "space", "context_pk": self.space.pk},
            )
        )
        self.assertEqual(outsider.status_code, 200)
        self.assertEqual(outsider.json()["results"], [])

    def test_acting_for_space_is_revalidated_server_side(self):
        point = self._question(client_reference="j7-space-response")
        self.client.force_login(self.member)
        url = reverse("conversations-api:point-respond", kwargs={"point_pk": point.pk})

        denied = self.client.post(
            url,
            {
                "value": "Au nom de l’Espace",
                "client_reference": "j7-space-denied",
                "represented_space_id": str(self.space.pk),
            },
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        grant_space_role(
            profile=self.member,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
            source="j7-space-response",
        )
        accepted = self.client.post(
            url,
            {
                "value": "Au nom de l’Espace",
                "client_reference": "j7-space-accepted",
                "represented_space_id": str(self.space.pk),
            },
            content_type="application/json",
        )
        self.assertEqual(accepted.status_code, 200)
        response = point.responses.get(pk=accepted.json()["id"])
        self.assertEqual(response.actor, self.member)
        self.assertEqual(response.represented_space, self.space)

    def test_web_invitation_can_be_declined_without_revealing_detail(self):
        invitation = create_conversation_invitation(
            actor=self.owner,
            conversation=self.conversation,
            invitee=self.outsider,
            client_reference="j7-web-invite",
        )
        self.client.force_login(self.outsider)
        listing = self.client.get(reverse("conversations:list"))
        self.assertContains(listing, "Invitations")
        response = self.client.post(
            reverse("conversations:invitation-respond", kwargs={"invitation_pk": invitation.pk}),
            {"decision": "decline"},
        )
        self.assertRedirects(response, reverse("conversations:list"))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ConversationInvitationStatus.DECLINED)

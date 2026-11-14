"""C3 end-to-end contracts: canonical writes, authority, idempotence and drafts."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import Conversation, ConversationContextKind
from .point_models import ConversationPoint, ConversationPointKind, ConversationPointResponseMode, ConversationResponseVisibility, PointExchangeEntry
from .point_services import (
    create_exchange_entry, create_point, resolve_point,
    point_visible_to, point_response_allowed, submit_point_response,
)
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationC3CompositionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="c3-owner", password="StrongPass2026!")
        self.member = User.objects.create_user(username="c3-member", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="c3-outsider", password="StrongPass2026!")
        self.space = Organization.objects.create(name="C3 Espace", created_by=self.owner)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.owner, title="C3 Activité",
        )
        grant_activity_role(
            profile=self.owner, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner, source="c3-activity",
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(
            actor=self.owner, conversation=self.conversation, profile=self.member,
        )
        self.audience = create_audience_set(
            actor=self.owner, conversation=self.conversation, label="Équipe",
        )
        add_audience_rule(
            actor=self.owner, audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE, profile=self.member,
        )

    def _url(self, conversation=None):
        return reverse("conversations-api:compose", kwargs={
            "pk": (conversation or self.conversation).pk,
        })

    def _post(self, payload, *, conversation=None):
        return self.client.post(
            self._url(conversation), json.dumps(payload),
            content_type="application/json",
        )

    def test_owner_capabilities_and_member_read_only_are_server_owned(self):
        self.client.force_login(self.owner)
        owner = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        ))
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(owner["Cache-Control"], "private, no-store")
        capabilities = owner.json()["composer"]
        self.assertTrue(capabilities["can_create"])
        self.assertIn("poll", capabilities["allowed_kinds"])
        self.assertEqual(capabilities["default_audience_id"], str(self.audience.pk))
        self.assertEqual(capabilities["text_mode"], "information")

        self.client.force_login(self.member)
        member = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        ))
        self.assertEqual(member.status_code, 200)
        self.assertFalse(member.json()["composer"]["can_create"])
        self.assertIsNone(member.json()["composer"]["text_mode"])
        self.assertEqual(member.json()["composer"]["audiences"], [])

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        )).status_code, 404)

    def test_publishing_text_retries_once_and_blocks_reference_reuse(self):
        self.client.force_login(self.owner)
        payload = {
            "mode": "text",
            "body": "Rendez-vous à 17 h",
            "client_reference": "c3-text-idempotent",
        }
        first = self._post(payload)
        second = self._post(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(
            ConversationPoint.objects.filter(conversation=self.conversation).count(), 1,
        )
        point = ConversationPoint.objects.get(pk=first.json()["id"])
        self.assertEqual(point.body, "Rendez-vous à 17 h")
        self.assertEqual(point.visibility_audience, self.audience)
        changed = self._post({**payload, "body": "Autre information"})
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(ConversationPoint.objects.count(), 1)

        self.client.force_login(self.member)
        denied = self._post({**payload, "client_reference": "c3-member-denied"})
        self.assertEqual(denied.status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self._post(payload).status_code, 404)

    def test_poll_confirmation_and_second_audience_require_an_explicit_choice(self):
        second_audience = create_audience_set(
            actor=self.owner, conversation=self.conversation, label="Direction",
        )
        self.client.force_login(self.owner)
        preview = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        )).json()["composer"]
        self.assertTrue(preview["audience_selection_required"])
        payload = {
            "mode": "point", "kind": "poll", "title": "Quelle heure ?",
            "options": ["14 h", "15 h"],
            "client_reference": "c3-poll",
        }
        self.assertEqual(self._post(payload).status_code, 400)
        result = self._post({**payload, "audience_id": str(second_audience.pk)})
        self.assertEqual(result.status_code, 200)
        poll = ConversationPoint.objects.get(pk=result.json()["point_id"])
        self.assertEqual(poll.kind, "poll")
        self.assertEqual(poll.response_mode, "single_choice")
        self.assertEqual(poll.visibility_audience, second_audience)
        self.assertEqual(poll.options.count(), 2)
        # Recipients are targeted; the author is not silently excluded.
        self.assertTrue(point_visible_to(self.owner, poll))
        self.assertTrue(point_response_allowed(self.owner, poll))
        self.assertFalse(point_visible_to(self.member, poll))
        choice = poll.options.order_by("position").first()
        vote = submit_point_response(
            actor=self.owner, point=poll, value=str(choice.pk),
            client_reference="c3-author-vote",
        )
        self.assertEqual(vote.actor_id, self.owner.pk)
        self.assertEqual(poll.responses.count(), 1)
        self.assertEqual(
            self._post({
                "mode": "point", "kind": "confirmation", "title": "Vous serez là ?",
                "audience_id": str(self.audience.pk),
                "client_reference": "c3-confirmation",
            }).status_code, 200,
        )
        self.assertEqual(
            self._post({
                **payload, "audience_id": str(self.audience.pk),
                "client_reference": "c3-other-audience",
            }).status_code, 200,
        )

    def test_plain_text_contributes_to_unique_exchange_not_a_new_point(self):
        self.client.force_login(self.owner)
        started = self._post({
            "mode": "point", "kind": "exchange", "title": "Questions à partager",
            "client_reference": "c3-exchange-start",
        })
        self.assertEqual(started.status_code, 200)
        point_id = started.json()["point_id"]
        self.client.force_login(self.member)
        detail = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        )).json()
        self.assertEqual(detail["composer"]["text_mode"], "exchange")
        self.assertEqual(detail["composer"]["default_exchange_point_id"], point_id)
        payload = {
            "mode": "text", "body": "Je confirme la préparation.",
            "client_reference": "c3-exchange-message",
        }
        first = self._post(payload)
        replay = self._post(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["kind"], "exchange")
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(ConversationPoint.objects.count(), 1)
        self.assertEqual(PointExchangeEntry.objects.count(), 1)
        self.assertEqual(
            self._post({**payload, "body": "Message différent"}).status_code, 400,
        )
        self.assertEqual(PointExchangeEntry.objects.count(), 1)
        detail = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        )).json()
        points = detail["points"] + detail["essential"] + detail["elsewhere"]
        item = next(item for item in points if item["id"] == point_id)
        self.assertEqual(item["exchange_preview"][0]["body"], payload["body"])

    def test_confirmed_exchange_retry_after_resolution_is_idempotent(self):
        self.client.force_login(self.owner)
        started = self._post({
            "mode": "point", "kind": "exchange",
            "title": "Coordination", "client_reference": "c3-replay-start",
        })
        self.assertEqual(started.status_code, 200)
        point_id = started.json()["point_id"]
        payload = {
            "mode": "text", "point_id": point_id,
            "body": "Message reçu", "client_reference": "c3-replay-entry",
        }
        self.client.force_login(self.member)
        first = self._post(payload)
        self.assertEqual(first.status_code, 200)

        self.client.force_login(self.owner)
        resolve_point(
            actor=self.owner, point=ConversationPoint.objects.get(pk=point_id),
            summary="Coordination terminée",
        )
        self.client.force_login(self.member)
        replay = self._post(payload)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["id"], first.json()["id"])
        self.assertEqual(PointExchangeEntry.objects.filter(point_id=point_id).count(), 1)

        # A fresh intent is not a retry and must remain blocked.
        fresh = self._post({**payload, "client_reference": "c3-replay-new"})
        self.assertEqual(fresh.status_code, 403)
        self.assertEqual(PointExchangeEntry.objects.filter(point_id=point_id).count(), 1)

        self.client.force_login(self.outsider)
        self.assertEqual(self._post(payload).status_code, 404)

    def test_implicit_exchange_send_replay_does_not_create_information(self):
        self.client.force_login(self.owner)
        started = self._post({
            "mode": "point", "kind": "exchange", "title": "Équipe",
            "client_reference": "c3-implicit-exchange",
        })
        self.assertEqual(started.status_code, 200)
        point_id = started.json()["point_id"]
        self.client.force_login(self.member)
        payload = {
            "mode": "text", "body": "Oui, cela avance.",
            "client_reference": "c3-implicit-message",
        }
        first = self._post(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["point_id"], point_id)

        self.client.force_login(self.owner)
        resolve_point(
            actor=self.owner, point=ConversationPoint.objects.get(pk=point_id),
            summary="Discussion terminée",
        )
        self.client.force_login(self.member)
        replay = self._post(payload)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["id"], first.json()["id"])
        self.assertEqual(replay.json()["kind"], "exchange")
        self.assertEqual(ConversationPoint.objects.count(), 1)
        self.assertEqual(PointExchangeEntry.objects.count(), 1)
        changed = self._post({**payload, "body": "Texte différent"})
        self.assertEqual(changed.status_code, 400)
        self.assertEqual(PointExchangeEntry.objects.count(), 1)

    def test_direct_profile_conversation_is_composable_only_after_owner_ensures_it(self):
        # Consent is established by the domain before the UI opens this
        # Conversation. The public Profile route cannot create a DM.
        direct = ensure_context_conversation(
            actor=self.owner, kind=ConversationContextKind.DIRECT,
            direct_profile_a=self.owner, direct_profile_b=self.member,
        )
        self.client.force_login(self.member)
        result = self._post({
            "mode": "text", "body": "Préparons cette action.",
            "client_reference": "c3-direct-existing",
        }, conversation=direct)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            ConversationPoint.objects.get(pk=result.json()["point_id"]).conversation,
            direct,
        )
        self.client.force_login(self.outsider)
        denied = self._post({
            "mode": "text", "body": "Je ne suis pas dans cet échange.",
            "client_reference": "c3-direct-outsider",
        }, conversation=direct)
        self.assertEqual(denied.status_code, 404)

    def test_c3_private_exchange_preview_never_leaks_other_people_text(self):
        another = User.objects.create_user(
            username="c3-another", password="StrongPass2026!",
        )
        activate_participation(
            actor=self.owner, conversation=self.conversation, profile=another,
        )
        add_audience_rule(
            actor=self.owner, audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE, profile=another,
        )
        point = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.EXCHANGE,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Échange privé",
            visibility_audience=self.audience,
            response_audience=self.audience,
            response_visibility=ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES,
        )
        create_exchange_entry(
            actor=self.member, point=point,
            body="Contenu privé de la réponse de membre 1",
            client_reference="c3-private-message-1",
        )
        self.client.force_login(another)
        detail = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        ))
        self.assertEqual(detail.status_code, 200)
        entries = [
            entry for key in ("points", "essential", "elsewhere")
            for item in detail.json()[key] if item["id"] == str(point.pk)
            for entry in item["exchange_preview"]
        ]
        self.assertEqual(entries, [])
        html = self.client.get(reverse(
            "conversations:detail", kwargs={"pk": self.conversation.pk},
        ))
        self.assertNotContains(html, "Contenu privé de la réponse de membre 1")
        self.client.force_login(self.member)
        detail = self.client.get(reverse(
            "conversations-api:detail", kwargs={"pk": self.conversation.pk},
        )).json()
        self.assertTrue(any(
            entry["body"] == "Contenu privé de la réponse de membre 1"
            for key in ("points", "essential", "elsewhere")
            for item in detail[key] if item["id"] == str(point.pk)
            for entry in item["exchange_preview"]
        ))

    def test_context_ensure_reuses_one_conversation_and_requires_manage_authority(self):
        grant_space_role(
            profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner, source="c3-space",
        )
        context = {
            "kind": "space", "context_pk": str(self.space.pk),
        }
        url = reverse("conversations-api:context-ensure", kwargs=context)
        self.client.force_login(self.member)
        no_permission = self.client.post(url, {}, content_type="application/json")
        self.assertEqual(no_permission.status_code, 403)

        self.client.force_login(self.owner)
        decision = self.client.get(
            reverse("conversations-api:by-context", kwargs=context),
        ).json()
        self.assertTrue(decision["can_ensure"])
        before = Conversation.objects.count()
        opened = self.client.post(url, {}, content_type="application/json")
        again = self.client.post(url, {}, content_type="application/json")
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["id"], again.json()["id"])
        self.assertEqual(Conversation.objects.count(), before + 1)

        self.assertEqual(self.client.post(
            reverse("conversations-api:context-ensure", kwargs={
                "kind": "direct", "context_pk": str(self.member.pk),
            }), {}, content_type="application/json",
        ).status_code, 403)

    def test_represented_space_is_checked_against_context_and_mandate(self):
        grant_space_role(
            profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner, source="c3-representation",
        )
        self.client.force_login(self.owner)
        accepted = self._post({
            "mode": "text", "body": "Au nom de notre Espace",
            "represented_space_id": str(self.space.pk),
            "client_reference": "c3-space-publish",
        })
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(
            ConversationPoint.objects.get(pk=accepted.json()["id"]).represented_space,
            self.space,
        )
        other = Organization.objects.create(name="Étranger C3", created_by=self.outsider)
        rejected = self._post({
            "mode": "text", "body": "Publier ailleurs",
            "represented_space_id": str(other.pk),
            "client_reference": "c3-wrong-space",
        })
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(ConversationPoint.objects.count(), 1)

    def test_web_compose_keeps_invalid_draft_and_focuses_success(self):
        self.client.force_login(self.owner)
        url = reverse("conversations:compose", kwargs={"pk": self.conversation.pk})
        invalid = self.client.post(url, {
            "mode": "point", "kind": "poll", "title": "",
            "options": "14 h\n15 h", "client_reference": "c3-web-draft",
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "c3-web-draft")
        self.assertContains(invalid, "14 h")
        success = self.client.post(url, {
            "mode": "text", "body": "Message depuis le Web",
            "client_reference": "c3-web-valid",
        })
        self.assertEqual(success.status_code, 302)
        self.assertIn("focus=", success["Location"])
        self.assertEqual(
            ConversationPoint.objects.filter(client_reference="c3-web-valid").count(), 1,
        )

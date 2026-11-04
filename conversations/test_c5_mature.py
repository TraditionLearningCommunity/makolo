"""C5: owner-checked history, search, continuation and personal UX contracts."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind, ConversationHistoryPolicy, ConversationLifecycle
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_exchange_entry, create_point, point_visible_to, supersede_point
from .services import activate_participation, ensure_context_conversation, transition_conversation


User = get_user_model()


class ConversationC5MatureTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username='c5-manager', password='StrongPass2026!')
        self.member = User.objects.create_user(username='c5-member', password='StrongPass2026!')
        self.other = User.objects.create_user(username='c5-other', password='StrongPass2026!')
        self.outside = User.objects.create_user(username='c5-outside', password='StrongPass2026!')
        self.space = Organization.objects.create(name='C5 Coordination', created_by=self.manager)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.manager, title='C5 Activity',
        )
        grant_activity_role(
            profile=self.manager, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.manager, source='c5',
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        for user in (self.member, self.other):
            activate_participation(
                actor=self.manager, conversation=self.conversation, profile=user,
            )

    def _point(self, title, **kwargs):
        return create_point(
            actor=self.manager, conversation=self.conversation,
            kind=kwargs.pop('kind', ConversationPointKind.INFORMATION),
            title=title, **kwargs,
        )

    def _audience(self, user, label):
        audience = create_audience_set(
            actor=self.manager, conversation=self.conversation, label=label,
        )
        add_audience_rule(
            actor=self.manager, audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=user,
        )
        return audience

    def _history(self, *, section='all', limit=25, cursor=None, query=None):
        params = {'section': section, 'limit': limit}
        if cursor is not None:
            params['cursor'] = cursor
        if query is not None:
            params['q'] = query
        return self.client.get(
            reverse('conversations-api:point-depth', kwargs={'pk': self.conversation.pk}),
            params,
        )

    def test_long_conversation_152_points_continues_without_duplicate_or_limit_50(self):
        for i in range(152):
            self._point('Étape %03d' % i)
        self.client.force_login(self.member)
        seen = set()
        cursor = None
        pages = 0
        while True:
            response = self._history(limit=23, cursor=cursor)
            self.assertEqual(response.status_code, 200, response.content)
            page = response.json()
            ids = [entry['id'] for entry in page['results']]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(seen.isdisjoint(ids))
            seen.update(ids)
            pages += 1
            cursor = page['next_cursor']
            if cursor is None:
                break
            self.assertLess(pages, 15)
        self.assertEqual(len(seen), 152)
        self.assertGreater(pages, 5)

    def test_history_cursor_cannot_replay_for_another_viewer_query_or_filter(self):
        self._point('Coordination 1')
        self._point('Coordination 2')
        self._point('Coordination 3')
        self.client.force_login(self.member)
        first = self._history(limit=1)
        self.assertEqual(first.status_code, 200)
        cursor = first.json()['next_cursor']
        self.assertIsNotNone(cursor)
        self.assertEqual(self._history(limit=1, cursor=cursor).status_code, 200)
        self.assertEqual(self._history(limit=1, cursor=cursor, query='autre').status_code, 400)
        self.assertEqual(self._history(limit=2, cursor=cursor).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self._history(limit=1, cursor=cursor).status_code, 400)
        self.client.force_login(self.outside)
        self.assertEqual(self._history(limit=1, cursor=cursor).status_code, 404)

    def test_search_reads_only_audience_authorized_points_and_entries(self):
        only_member = self._audience(self.member, 'Membre')
        only_other = self._audience(self.other, 'Autre')
        visible = self._point('Dossier secret membre', visibility_audience=only_member)
        private = self._point('Dossier secret autre', visibility_audience=only_other)
        exchange = self._point(
            'Échange de détails',
            kind=ConversationPointKind.EXCHANGE,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            response_visibility='respondent_and_authorities',
        )
        create_exchange_entry(
            actor=self.member, point=exchange,
            body='Coordonnées confidentielles du membre',
        )
        self.client.force_login(self.member)
        accessible = self._history(query='secret')
        self.assertEqual(accessible.status_code, 200)
        self.assertEqual(
            [entry['id'] for entry in accessible.json()['results']],
            [str(visible.pk)],
        )
        private_entry = self._history(query='Coordonnées confidentielles')
        self.assertEqual(
            [entry['id'] for entry in private_entry.json()['results']],
            [str(exchange.pk)],
        )
        self.client.force_login(self.other)
        other = self._history(query='secret')
        self.assertEqual(
            [entry['id'] for entry in other.json()['results']],
            [str(private.pk)],
        )
        no_entry = self._history(query='Coordonnées confidentielles')
        self.assertEqual(no_entry.json()['results'], [])

    def test_history_since_join_and_rejoin_is_consistent_with_direct_focus(self):
        self.conversation.history_policy = ConversationHistoryPolicy.FROM_JOIN
        self.conversation.save(update_fields=['history_policy', 'updated_at'])
        old = self._point('Avant arrivée')
        late = User.objects.create_user(username='c5-late', password='StrongPass2026!')
        participation = activate_participation(
            actor=self.manager, conversation=self.conversation, profile=late,
        )
        joined = participation.joined_at
        activate_participation(
            actor=self.manager, conversation=self.conversation, profile=late,
        )
        participation.refresh_from_db()
        self.assertEqual(participation.joined_at, joined)
        new = self._point('Après arrivée')
        self.assertFalse(point_visible_to(late, old))
        self.assertTrue(point_visible_to(late, new))
        self.client.force_login(late)
        page = self._history()
        self.assertEqual(
            [entry['id'] for entry in page.json()['results']],
            [str(new.pk)],
        )
        focus = self.client.get(
            reverse('conversations-api:detail', kwargs={'pk': self.conversation.pk}),
            {'focus_point': str(old.pk)},
        )
        self.assertEqual(focus.status_code, 200)
        self.assertIsNone(focus.json()['focused_point'])
        self.assertEqual(self._history(query='Avant arrivée').json()['results'], [])

    def test_history_resolved_superseded_and_draft_not_public(self):
        old = self._point('Ancien horaire')
        newer = self._point('Horaire confirmé', publish=False)
        supersede_point(actor=self.manager, old_point=old, new_point=newer)
        draft = self._point('Brouillon réservé', publish=False)
        self.client.force_login(self.member)
        page = self._history(section='history')
        self.assertEqual(
            [row['id'] for row in page.json()['results']], [str(old.pk)],
        )
        all_page = self._history()
        self.assertIn(str(newer.pk), [row['id'] for row in all_page.json()['results']])
        self.assertNotIn(str(draft.pk), [row['id'] for row in all_page.json()['results']])
        search = self._history(query='Ancien horaire')
        self.assertEqual(search.json()['results'][0]['lifecycle'], 'superseded')

    def test_archived_web_and_api_query_stay_personal_not_shared(self):
        self._point('Décision coordonnée')
        self.client.force_login(self.member)
        action_url = reverse(
            'conversations:personal-state', kwargs={'pk': self.conversation.pk},
        )
        action = self.client.post(action_url, {'action': 'archive'})
        self.assertEqual(action.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lifecycle, ConversationLifecycle.OPEN)
        all_list = self.client.get(reverse('conversations-api:list'))
        self.assertNotIn(
            str(self.conversation.pk),
            [row['id'] for row in all_list.json()['results']],
        )
        archived = self.client.get(
            reverse('conversations-api:list'), {'tab': 'archived', 'q': 'Décision'},
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(
            [row['id'] for row in archived.json()['results']],
            [str(self.conversation.pk)],
        )
        web = self.client.get(
            reverse('conversations:list'), {'tab': 'archived'},
        )
        self.assertContains(web, 'C5 Activity')
        self.client.post(action_url, {'action': 'archive'})
        self.assertIn(
            str(self.conversation.pk),
            [row['id'] for row in self.client.get(
                reverse('conversations-api:list')
            ).json()['results']],
        )

    def test_closed_conversation_has_no_stale_attention_or_response_controls(self):
        from .attention import point_attention_reason

        expected = self._audience(self.member, 'Réponse attendue')
        point = self._point(
            'Confirmer le rendez-vous',
            kind=ConversationPointKind.CONFIRMATION,
            response_mode=ConversationPointResponseMode.BOOLEAN,
            expected_action_audience=expected,
            response_audience=expected,
        )
        self.assertEqual(point_attention_reason(self.member, point), 'respond')
        transition_conversation(
            actor=self.manager, conversation=self.conversation,
            lifecycle=ConversationLifecycle.CLOSED,
        )
        point.conversation.refresh_from_db()
        self.assertIsNone(point_attention_reason(self.member, point))
        self.client.force_login(self.member)
        detail = self.client.get(reverse(
            'conversations-api:detail', kwargs={'pk': self.conversation.pk},
        ))
        self.assertEqual(detail.status_code, 200)
        for section in ('points', 'essential', 'elsewhere'):
            for item in detail.json()[section]:
                if item['id'] == str(point.pk):
                    self.assertFalse(item['can_respond'])

    def test_closed_conversation_read_only_and_history_still_available(self):
        point = self._point('État établi')
        transition_conversation(
            actor=self.manager, conversation=self.conversation,
            lifecycle=ConversationLifecycle.CLOSED,
        )
        self.client.force_login(self.member)
        detail = self.client.get(reverse(
            'conversations-api:detail', kwargs={'pk': self.conversation.pk},
        ))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.json()['composer']['can_create'])
        rows = detail.json()['points'] + detail.json()['essential'] + detail.json().get('elsewhere', [])
        for row in rows:
            self.assertFalse(row['can_respond'])
        denied_response = self.client.post(
            reverse('conversations-api:point-respond', kwargs={'point_pk': point.pk}),
            {'value': 'reply after closing'},
        )
        self.assertEqual(denied_response.status_code, 400)
        history = self._history()
        self.assertEqual(
            [item['id'] for item in history.json()['results']], [str(point.pk)],
        )
        invalid = self.client.post(
            reverse('conversations:personal-state', kwargs={'pk': self.conversation.pk}),
            {'action': 'unsupported'},
        )
        self.assertEqual(invalid.status_code, 404)

    def test_replacement_does_not_reveal_hidden_successor_id(self):
        member_only = self._audience(self.member, 'Only member')
        other_only = self._audience(self.other, 'Only other')
        old = self._point('Ancien Point partagé')
        hidden_successor = self._point(
            'Nouveau contenu privé', visibility_audience=other_only,
            publish=False,
        )
        supersede_point(
            actor=self.manager, old_point=old, new_point=hidden_successor,
        )
        self.client.force_login(self.member)
        page = self._history(query='Ancien Point')
        self.assertEqual(page.status_code, 200)
        row = page.json()['results'][0]
        self.assertEqual(row['id'], str(old.pk))
        self.assertIsNone(row['replaced_by_point_id'])
        html = self.client.get(
            reverse('conversations:history', kwargs={'pk': self.conversation.pk}),
            {'section': 'history', 'q': 'Ancien Point'},
        )
        self.assertNotContains(html, str(hidden_successor.pk))
        self.assertNotContains(html, 'Voir le Point actuel')
        self.client.force_login(self.other)
        other = self._history(query='Ancien Point')
        self.assertEqual(other.status_code, 200)
        self.assertEqual(
            other.json()['results'][0]['replaced_by_point_id'],
            str(hidden_successor.pk),
        )
        self.assertTrue(point_visible_to(self.other, hidden_successor))

    def test_response_result_does_not_expose_private_count_to_peer(self):
        private_audience = self._audience(self.member, 'Membre répondant')
        point = self._point(
            'Confirmation privée',
            kind=ConversationPointKind.CONFIRMATION,
            response_mode=ConversationPointResponseMode.BOOLEAN,
            response_audience=private_audience,
            response_visibility='respondent_and_authorities',
        )
        from .point_services import submit_point_response
        submit_point_response(
            actor=self.member, point=point, value=True,
            client_reference='c5-respond-private',
        )
        self.client.force_login(self.other)
        response = self.client.get(reverse(
            'conversations-api:point-depth',
            kwargs={'pk': self.conversation.pk},
        ), {'section': 'all', 'q': 'Confirmation privée'})
        self.assertEqual(response.status_code, 200)
        result = response.json()['results'][0]['response_status']
        self.assertEqual(result['responded'], False)
        self.assertIsNone(result['response_count'])
        self.client.force_login(self.member)
        own = self._history(query='Confirmation privée').json()['results'][0]
        self.assertTrue(own['response_status']['responded'])
        self.assertIsNone(own['response_status']['response_count'])
        self.client.force_login(self.manager)
        manager = self._history(query='Confirmation privée').json()['results'][0]
        self.assertEqual(manager['response_status']['response_count'], 1)

    def test_private_resolution_never_leaks_via_history_list_search_or_web(self):
        from .point_services import resolve_point

        authority_audience = self._audience(self.manager, 'Résolution des autorités')
        point = self._point(
            'Point de décision',
            kind=ConversationPointKind.CONFIRMATION,
            response_mode=ConversationPointResponseMode.BOOLEAN,
            resolution_audience=authority_audience,
        )
        resolve_point(
            actor=self.manager, point=point, summary='Conclusion réservée aux autorités',
        )

        self.client.force_login(self.member)
        search = self._history(query='Conclusion réservée')
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()['results'], [])
        permitted_point = self._history(query='Point de décision')
        self.assertEqual(permitted_point.status_code, 200)
        self.assertEqual(permitted_point.json()['results'][0]['id'], str(point.pk))
        self.assertFalse(
            permitted_point.json()['results'][0]['resolution_summary']
        )
        listing = self.client.get(
            reverse('conversations-api:list'), {'q': 'Conclusion réservée'},
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['results'], [])
        normal_list = self.client.get(reverse('conversations-api:list'))
        self.assertNotIn('Conclusion réservée', normal_list.content.decode())
        web = self.client.get(
            reverse('conversations:history', kwargs={'pk': self.conversation.pk}),
            {'section': 'all', 'q': 'Point de décision'},
        )
        self.assertEqual(web.status_code, 200)
        self.assertNotContains(web, 'Conclusion réservée aux autorités')

        self.client.force_login(self.manager)
        allowed = self._history(query='Conclusion réservée')
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()['results'][0]['id'], str(point.pk))
        self.assertEqual(
            allowed.json()['results'][0]['resolution_summary'],
            'Conclusion réservée aux autorités',
        )

    def test_web_history_search_is_accessible_and_cursor_preserves_filter(self):
        for i in range(27):
            self._point('Contrôle %02d' % i)
        self.client.force_login(self.member)
        url = reverse('conversations:history', kwargs={'pk': self.conversation.pk})
        result = self.client.get(url, {'section': 'all', 'q': 'Contrôle'})
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'Retrouver un Point')
        self.assertContains(result, 'Voir les Points suivants')
        self.assertContains(result, 'cursor=')
        self.assertContains(result, 'q=Contr%C3%B4le')
        self.client.force_login(self.outside)
        denied = self.client.get(url)
        self.assertIn(denied.status_code, (403, 404))

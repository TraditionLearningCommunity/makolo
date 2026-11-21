"""C4 full owner contract for FormRequest, media and rich Exchange depth."""
import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization
from questionnaires.models import FormRequest, QuestionType
from questionnaires.services import (
    add_question, create_form, create_form_version, publish_form_version,
    save_response, submit_response,
)

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .form_models import ConversationPointFormRequest
from .media_models import ConversationPointAttachment
from .point_models import ConversationPoint, ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point, resolve_point
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationC4RichTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='c4-owner', password='StrongPass2026!')
        self.member = User.objects.create_user(username='c4-member', password='StrongPass2026!')
        self.other = User.objects.create_user(username='c4-other', password='StrongPass2026!')
        self.outsider = User.objects.create_user(username='c4-outsider', password='StrongPass2026!')
        self.space = Organization.objects.create(name='C4 Espace', created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title='C4 Activity')
        grant_activity_role(
            profile=self.owner, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner, source='c4',
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        for profile in (self.member, self.other):
            activate_participation(actor=self.owner, conversation=self.conversation, profile=profile)
        self.audience = create_audience_set(
            actor=self.owner, conversation=self.conversation, label='Destinataires',
        )
        add_audience_rule(
            actor=self.owner, audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE, profile=self.member,
        )

    def _api(self, name, **kwargs):
        return reverse('conversations-api:' + name, kwargs={
            **({'pk': self.conversation.pk} if name in {
                'media-upload', 'form-compose', 'form-options', 'detail',
            } else {}),
            **kwargs,
        })

    def _form_request(self):
        self.client.force_login(self.owner)
        url = self._api('form-compose')
        return self.client.post(url, data=json.dumps({
            'title': 'Préparation collective',
            'questions': ['Quel matériel ?', 'Quel horaire ?'],
            'audience_id': str(self.audience.pk),
            'client_reference': 'c4-form-unique',
        }), content_type='application/json')

    def test_form_preparation_is_canonical_idempotent_and_returns_to_recipient(self):
        first = self._form_request()
        self.assertEqual(first.status_code, 200, first.content)
        second = self._form_request()
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()['point_id'], second.json()['point_id'])
        point = ConversationPoint.objects.get(pk=first.json()['point_id'])
        self.assertEqual(point.kind, ConversationPointKind.FORM_REQUEST)
        self.assertEqual(point.form_request_links.count(), 1)
        link = point.form_request_links.get()
        self.assertEqual(link.target_profile, self.member)
        self.assertIsNone(link.form_request.journey_id)
        self.assertEqual(link.form_request.form_version.questions.count(), 2)
        self.assertEqual(FormRequest.objects.count(), 1)
        self.client.force_login(self.member)
        detail = self.client.get(self._api('detail')).json()
        row = next(item for section in ('points', 'essential', 'elsewhere')
                   for item in detail[section] if item['id'] == str(point.pk))
        self.assertEqual(row['form_request']['id'], str(link.form_request_id))
        target = self.client.get(
            '/api/v1/questionnaires/requests/%s/' % link.form_request_id
        )
        self.assertEqual(target.status_code, 200)
        self.client.force_login(self.other)
        detail = self.client.get(self._api('detail')).json()
        self.assertFalse(any(
            item['id'] == str(point.pk)
            for section in ('points', 'essential', 'elsewhere')
            for item in detail[section]
        ))
        self.assertEqual(self.client.get(
            '/api/v1/questionnaires/requests/%s/' % link.form_request_id
        ).status_code, 404)
        self.assertEqual(
            ConversationPointFormRequest.objects.filter(point=point).count(), 1,
        )
        self.client.force_login(self.member)
        save_response(
            request=link.form_request, actor=self.member,
            answers={'question_1': 'Un micro', 'question_2': '15 h'},
        )
        submit_response(request=link.form_request, actor=self.member)
        link.form_request.refresh_from_db()
        self.assertEqual(link.form_request.status, 'completed')

    def test_form_requires_activity_authority_and_rejects_unrelated_version(self):
        self.client.force_login(self.owner)
        available = self.client.get(self._api('form-options'))
        self.assertEqual(available.status_code, 200)
        self.assertTrue(available.json()['can_prepare'])
        form = create_form(
            actor=self.owner, activity=self.activity, key='existing-c4', title='Formulaire',
        )
        version = create_form_version(form=form, actor=self.owner)
        add_question(
            form_version=version, actor=self.owner, key='topic',
            label='Votre sujet ?', position=0, required=True,
            question_type=QuestionType.SHORT_TEXT,
        )
        publish_form_version(form_version=version, actor=self.owner)
        options = self.client.get(self._api('form-options')).json()['results']
        self.assertIn(str(version.pk), [item['id'] for item in options])
        accepted = self.client.post(self._api('form-compose'), json.dumps({
            'title': 'Répondre', 'form_version_id': str(version.pk),
            'audience_id': str(self.audience.pk),
            'client_reference': 'c4-form-reuse',
        }), content_type='application/json')
        self.assertEqual(accepted.status_code, 200)
        self.client.force_login(self.member)
        self.assertFalse(self.client.get(self._api('form-options')).json()['can_prepare'])
        denied = self.client.post(self._api('form-compose'), json.dumps({
            'title': 'Intrusion', 'form_version_id': str(version.pk),
            'audience_id': str(self.audience.pk),
            'client_reference': 'c4-denied',
        }), content_type='application/json')
        self.assertEqual(denied.status_code, 403)

    def _media(self, *, data=b'consignes privees', filename='consignes.txt',
               mime='text/plain', ref='c4-private-media', kind='file', point_id=None):
        url = self._api('media-upload')
        payload = {
            'kind': kind, 'client_reference': ref,
            'file': SimpleUploadedFile(filename, data, content_type=mime),
        }
        if point_id:
            payload['point_id'] = str(point_id)
        return self.client.post(url, payload)

    def test_private_document_upload_download_idempotence_and_content_conflicts(self):
        self.client.force_login(self.owner)
        first = self._media()
        self.assertEqual(first.status_code, 200, first.content)
        second = self._media()
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()['attachment']['id'], second.json()['attachment']['id'])
        self.assertEqual(ConversationPointAttachment.objects.count(), 1)
        self.assertEqual(self._media(data=b'autre contenu').status_code, 400)
        attachment_id = first.json()['attachment']['id']
        download = reverse('conversations-api:attachment-download', kwargs={'attachment_pk': attachment_id})
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(download).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.client.force_login(self.owner)
        accepted = self.client.get(download)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted['Cache-Control'], 'private, no-store')
        self.assertEqual(accepted['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(accepted.streaming_content), b'consignes privees')

    def test_media_validates_signatures_without_creating_orphan_point(self):
        self.client.force_login(self.owner)
        point_count = ConversationPoint.objects.count()
        denied = self._media(
            kind='voice', filename='faux.webm', mime='audio/webm',
            data=b'not-really-audio', ref='c4-invalid-audio',
        )
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(ConversationPoint.objects.count(), point_count)
        allowed = self._media(
            kind='voice', filename='vocal.wav', mime='audio/wav',
            data=b'RIFF\x08\x00\x00\x00WAVE' + b'fmt ' + b'\x00'*24,
            ref='c4-valid-voice',
        )
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertEqual(allowed.json()['attachment']['kind'], 'voice')

    def test_exchange_entries_and_private_attachments_revalidate_visibility(self):
        self.client.force_login(self.owner)
        add_audience_rule(
            actor=self.owner, audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.owner,
        )
        exchange = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.EXCHANGE,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title='Questions', visibility_audience=self.audience,
            response_audience=self.audience,
            response_visibility='respondent_and_authorities',
        )
        self.client.force_login(self.member)
        first = self.client.post(
            reverse('conversations-api:exchange-entries', kwargs={'point_pk': exchange.pk}),
            json.dumps({'body': 'Un message privé', 'client_reference': 'c4-entry'}),
            content_type='application/json',
        )
        self.assertEqual(first.status_code, 200)
        attachment = self._media(
            kind='file', ref='c4-entry-upload',
            point_id=exchange.pk,
        )
        self.assertEqual(attachment.status_code, 200)
        own = self.client.get(reverse('conversations-api:exchange-entries', kwargs={'point_pk': exchange.pk}))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(len(own.json()['results']), 2)
        self.assertEqual(own.json()['results'][1]['attachments'][0]['id'], attachment.json()['attachment']['id'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(
            reverse('conversations-api:exchange-entries', kwargs={'point_pk': exchange.pk})
        ).status_code, 404)
        self.assertEqual(self.client.get(reverse(
            'conversations-api:attachment-download',
            kwargs={'attachment_pk': attachment.json()['attachment']['id']},
        )).status_code, 404)
        self.client.force_login(self.owner)
        view = self.client.get(reverse('conversations:exchange-detail', kwargs={'point_pk': exchange.pk}))
        self.assertEqual(view.status_code, 200)
        self.assertContains(view, 'Un message privé')
        self.assertContains(view, 'Discussion')

    def test_file_response_attaches_to_canonical_response_not_new_point(self):
        self.client.force_login(self.owner)
        point = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.REQUEST,
            response_mode=ConversationPointResponseMode.FILE,
            title='Joindre le document', visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
        )
        self.client.force_login(self.member)
        url = reverse('conversations-api:point-reply-media', kwargs={'point_pk': point.pk})
        def upload(data=b'contenu fourni', ref='c4-point-file'):
            return self.client.post(url, {
                'kind': 'file',
                'client_reference': ref,
                'file': SimpleUploadedFile(
                    'contenu.txt', data, content_type='text/plain',
                ),
            })
        first = upload()
        self.assertEqual(first.status_code, 200, first.content)
        again = upload()
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(first.json()['response_id'], again.json()['response_id'])
        self.assertEqual(first.json()['attachment']['id'], again.json()['attachment']['id'])
        self.assertEqual(ConversationPoint.objects.count(), 1)
        self.assertEqual(point.responses.count(), 1)
        attached = ConversationPointAttachment.objects.get(
            pk=first.json()['attachment']['id'],
        )
        self.assertEqual(attached.response_id, point.responses.first().pk)
        self.assertIsNone(attached.exchange_entry_id)
        self.assertEqual(upload(data=b'mauvais fichier').status_code, 400)

        self.client.force_login(self.owner)
        resolve_point(actor=self.owner, point=point, summary='Pièce reçue')
        self.client.force_login(self.member)
        self.assertEqual(upload().status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(upload(ref='c4-outside').status_code, 404)

    def test_voice_response_requires_signed_audio_and_correct_mode(self):
        self.client.force_login(self.owner)
        point = create_point(
            actor=self.owner, conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.VOICE,
            title='Répondre en vocal',
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
        )
        self.client.force_login(self.member)
        url = reverse('conversations-api:point-reply-media', kwargs={'point_pk': point.pk})
        sound = b'RIFF\x08\x00\x00\x00WAVEfmt ' + b'\x00' * 24
        invalid = self.client.post(url, {
            'kind': 'file', 'client_reference': 'c4-voice-mismatch',
            'file': SimpleUploadedFile(
                'fichier.txt', b'bonjour', content_type='text/plain',
            ),
        })
        self.assertEqual(invalid.status_code, 400)
        valid = self.client.post(url, {
            'kind': 'voice', 'client_reference': 'c4-voice-point',
            'file': SimpleUploadedFile(
                'vocal.wav', sound, content_type='audio/wav',
            ),
        })
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(point.responses.count(), 1)
        self.assertEqual(
            ConversationPointAttachment.objects.filter(
                point=point, response__isnull=False,
            ).count(), 1,
        )

    def test_web_form_and_media_actions_use_real_owners(self):
        self.client.force_login(self.owner)
        html = self.client.get(reverse('conversations:detail', kwargs={'pk': self.conversation.pk}))
        self.assertContains(html, 'Formulaire')
        self.assertContains(html, 'conversations-rich-composer.js')
        result = self.client.post(reverse('conversations:compose', kwargs={'pk': self.conversation.pk}), {
            'mode': 'form', 'title': 'Formulaire web',
            'questions': 'Votre nom ?', 'audience_id': str(self.audience.pk),
            'client_reference': 'c4-web-form',
        })
        self.assertEqual(result.status_code, 302)
        self.assertEqual(ConversationPointFormRequest.objects.count(), 1)

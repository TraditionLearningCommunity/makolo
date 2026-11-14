import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/space/space_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _Store implements ActorContextStore {
  ActorContext current = const PersonalActorContext();

  @override
  Future<ActorContext> readActorContext(String profileId) async => current;

  @override
  Future<void> writeActorContext(String profileId, ActorContext value) async {
    current = value;
  }

  @override
  Future<void> removeActorContext(String profileId) async {
    current = const PersonalActorContext();
  }
}

Map<String, dynamic> _source() => {
  'subject_kind': 'space',
  'subject_id': 'space-1',
  'slug': 'atelier',
  'variant': 'complete',
  'public_profile_enabled': true,
  'public_path': '/atelier/',
  'identity': {
    'name': 'Atelier collectif',
    'headline': 'Organisation',
    'bio': 'Présentation collective.',
    'location': 'Lubumbashi, CD',
    'links': [
      {'label': 'Site web', 'url': 'https://atelier.example.test'},
    ],
    'owner_details': {
      'email': 'prive@atelier.example.test',
      'phone': '+243810000000',
    },
  },
  'activities': [
    {
      'id': 'activity-public',
      'title': 'Atelier public',
      'status': 'Publié',
      'topic_codes': ['culture'],
    },
    {
      'id': 'activity-private',
      'title': 'Réunion interne',
      'status': 'Publié',
      'topic_codes': ['finance'],
    },
  ],
  'established': {'trust_verifications': const []},
  'issued': {'credential_summary': const []},
  'collectives': {
    'space_teams': ['Équipe interne'],
  },
  'topic_options': [
    {'code': 'culture', 'label': 'Culture'},
  ],
  'composition': {
    'schema_version': 1,
    'public_identity': {
      'name': 'Atelier collectif',
      'headline': 'Organisation',
      'bio': 'Présentation collective.',
      'location': 'Lubumbashi, CD',
      'links': [
        {'label': 'Site web', 'url': 'https://atelier.example.test'},
      ],
    },
    'public_ids': {
      'activities': ['activity-public'],
    },
    'public_trust': const [],
    'public_credentials': const [],
  },
};

void main() {
  testWidgets('Space Passport uses one owner fetch for all four variants', (
    tester,
  ) async {
    final store = _Store();
    final actor = await ActorContextController.restore(
      profileId: 'profile-1',
      store: store,
    );
    addTearDown(actor.dispose);
    await actor.selectSpace(SpaceActorIdentity(id: 'space-1', slug: 'atelier'));
    var fetches = 0;
    final tokens = MemoryTokenStore(
      session: const AuthSession(
        profileId: 'profile-1',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );
    final api = MakoloApiClient(
      baseUri: Uri.parse('https://makolo.invalid/'),
      tokenStore: tokens,
      dio: MockClient((request) async {
        if (request.url.path ==
            '/api/v1/organizations/workspaces/atelier/passport/') {
          fetches++;
          return MockResponse(
            jsonEncode({
              'meta': {
                'projection': 'space.passport',
                'schema_version': 1,
                'scope': 'space',
                'generated_at': '2026-11-03T08:00:00Z',
              },
              'data': _source(),
            }),
            200,
          );
        }
        throw StateError('Unexpected request');
      }).dio,
    );
    addTearDown(api.close);
    final runtime = AppRuntime(
      tokens: tokens,
      session: tokens.session,
      recovery: SessionRecoveryController(),
      actorContext: actor,
      api: api,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: SpacePassportScreen(runtime: runtime, slug: 'atelier'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Atelier collectif'), findsOneWidget);
    expect(find.byTooltip('Versions datées'), findsOneWidget);
    expect(find.byTooltip('PDF'), findsOneWidget);
    expect(fetches, 1);

    await tester.tap(find.text('Public'));
    await tester.pumpAndSettle();
    expect(find.text('Atelier collectif'), findsOneWidget);
    await tester.tap(find.text('Thématique'));
    await tester.pumpAndSettle();
    expect(find.text('Atelier collectif'), findsOneWidget);
    await tester.tap(find.text('Personnalisé'));
    await tester.pumpAndSettle();
    expect(fetches, 1);

    await tester.tap(find.byTooltip('Partager le Passeport'));
    await tester.pumpAndSettle();
    expect(find.text('Partager le PDF'), findsOneWidget);
    expect(find.text('Partager dans Makolo'), findsOneWidget);
    expect(find.text('Partager le lien public'), findsOneWidget);
    expect(find.text('Copier le lien du Passeport'), findsOneWidget);
    expect(find.text('Partager une ancienne version'), findsNothing);

    await tester.pageBack();
    await tester.pumpAndSettle();
    await actor.selectPersonal();
    await tester.pumpAndSettle();
    expect(find.text('Atelier collectif'), findsNothing);
    expect(
      find.text(
        'Impossible de consulter le Passeport de cet Espace actuellement.',
      ),
      findsOneWidget,
    );
  });
}

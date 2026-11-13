import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/actor_context.dart';
import 'package:makolo_mobile/app/runtime/actor_context_controller.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/app/session_recovery.dart';
import 'package:makolo_mobile/auth/token_store.dart';
import 'package:makolo_mobile/features/space/space_documents_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

import 'dio_testing.dart';
import 'fakes.dart';

class _LocalActorStore implements ActorContextStore {
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

void main() {
  testWidgets(
    'Space documents retain prior list on outage but revoke on 403 or switch',
    (tester) async {
      final actor = await ActorContextController.restore(
        profileId: 'profile-a',
        store: _LocalActorStore(),
      );
      addTearDown(actor.dispose);
      await actor.selectSpace(
        SpaceActorIdentity(id: 'space-a', slug: 'atelier'),
      );
      var failure = 0;
      final tokens = MemoryTokenStore(
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
      );
      final api = MakoloApiClient(
        baseUri: Uri.parse('https://makolo.invalid/'),
        tokenStore: tokens,
        dio: MockClient((request) async {
          expect(
            request.url.path,
            '/api/v1/organizations/workspaces/atelier/documents/',
          );
          if (failure != 0) {
            return MockResponse('{"detail":"owner unavailable"}', failure);
          }
          return MockResponse(
            jsonEncode({
              'space_id': 'space-a',
              'count': 1,
              'items': [
                {
                  'id': '00000000-0000-4000-8000-000000000001',
                  'title': 'Document déjà connu',
                  'visibility': 'restricted',
                  'latest_version': 1,
                },
              ],
              'can_manage': true,
              'has_more': false,
              'next_offset': 1,
            }),
            200,
          );
        }).dio,
      );
      addTearDown(api.close);
      final runtime = AppRuntime(
        tokens: tokens,
        session: const AuthSession(
          accessToken: 'access',
          refreshToken: 'refresh',
          profileId: 'profile-a',
        ),
        recovery: SessionRecoveryController(),
        actorContext: actor,
        api: api,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: SpaceDocumentsScreen(runtime: runtime, slug: 'atelier'),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Nos documents'), findsOneWidget);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('Document déjà connu'), findsOneWidget);
      expect(find.byTooltip('Ajouter'), findsOneWidget);
      expect(find.byTooltip('Rechercher'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);

      failure = 503;
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsOneWidget);
      expect(find.textContaining('dernière consultation'), findsOneWidget);
      expect(
        find.byTooltip('Ajouter'),
        findsNothing,
        reason: 'Old list never grants fresh upload authority',
      );

      failure = 403;
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsNothing);
      expect(find.textContaining('non accessibles'), findsOneWidget);

      await actor.selectPersonal();
      await tester.pumpAndSettle();
      expect(find.text('Document déjà connu'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
